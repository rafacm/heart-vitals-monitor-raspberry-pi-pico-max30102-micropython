from array import array
from utime import ticks_ms, ticks_diff

_DISP_W                  = 128
_WAV_TOP                 = 9       # first y pixel of waveform (below separator at y=8)
_WAV_H                   = 55      # y=9..63
_COMPUTE_INTERVAL_MS     = 2000    # BPM + SpO2 recompute cadence
_DRAW_INTERVAL_MS        = 300     # display refresh cadence
_NORM_RECOMPUTE_INTERVAL = 256     # samples between full min/max recompute
_HR_WINDOW_SIZE          = 250
_HR_SMOOTHING_WINDOW     = 15
_HR_BPM_BUFFER_SIZE      = 5
_HR_MIN_BPM              = 40
_HR_MAX_BPM              = 200
_HR_MIN_PEAK_MS          = 300
_IR_FINGER_THRESHOLD     = 10000
_IR_AVG_WINDOW           = 20
_SPO2_WINDOW             = 20

_HEART_LARGE = b'\x66\xFF\xFF\x7E\x3C\x18\x18\x00'
_HEART_SMALL = b'\x00\x66\x7E\x3C\x18\x18\x00\x00'


class _HRAlgorithm:
    """Integer-only heart-rate detection — ported from HeartRateMonitor."""

    def __init__(self):
        self._samples    = array('l', [0] * _HR_WINDOW_SIZE)
        self._timestamps = array('l', [0] * _HR_WINDOW_SIZE)
        self._n          = 0

        self._smooth_buf   = array('l', [0] * _HR_SMOOTHING_WINDOW)
        self._smooth_idx   = 0
        self._smooth_sum   = 0
        self._smooth_count = 0

        self._bpm_buf   = array('l', [0] * _HR_BPM_BUFFER_SIZE)
        self._bpm_count = 0

        # Pre-allocated working arrays to avoid per-call heap allocation
        self._sig = array('l', [0] * _HR_WINDOW_SIZE)
        self._ts  = array('l', [0] * _HR_WINDOW_SIZE)

    def reset(self):
        for i in range(_HR_WINDOW_SIZE):
            self._samples[i]    = 0
            self._timestamps[i] = 0
        self._n = 0

        for i in range(_HR_SMOOTHING_WINDOW):
            self._smooth_buf[i] = 0
        self._smooth_idx   = 0
        self._smooth_sum   = 0
        self._smooth_count = 0

        for i in range(_HR_BPM_BUFFER_SIZE):
            self._bpm_buf[i] = 0
        self._bpm_count = 0

    def _buf_get(self, buf, age):
        return buf[(self._n - 1 - age) % _HR_WINDOW_SIZE]

    def add_sample(self, ir):
        ts  = ticks_ms()
        idx = self._n % _HR_WINDOW_SIZE
        self._samples[idx]    = ir
        self._timestamps[idx] = ts
        self._n += 1

        old = self._smooth_buf[self._smooth_idx]
        self._smooth_buf[self._smooth_idx] = ir
        self._smooth_sum += ir - old
        self._smooth_idx = (self._smooth_idx + 1) % _HR_SMOOTHING_WINDOW
        if self._smooth_count < _HR_SMOOTHING_WINDOW:
            self._smooth_count += 1

    @staticmethod
    def _median(buf, n):
        tmp = [buf[i] for i in range(n)]
        for i in range(1, n):
            key = tmp[i]
            j = i - 1
            while j >= 0 and tmp[j] > key:
                tmp[j + 1] = tmp[j]
                j -= 1
            tmp[j + 1] = key
        mid = n // 2
        return tmp[mid] if n % 2 == 1 else (tmp[mid - 1] + tmp[mid]) // 2

    def calculate_heart_rate(self):
        filled = min(self._n, _HR_WINDOW_SIZE)
        if filled < _HR_SMOOTHING_WINDOW + 2:
            return None

        sig_len = filled
        sig     = self._sig
        ts      = self._ts
        half    = _HR_SMOOTHING_WINDOW // 2

        # Build integer moving-average smoothed signal (oldest → newest)
        for i in range(sig_len):
            age   = sig_len - 1 - i
            ts[i] = self._buf_get(self._timestamps, age)
            acc   = 0
            count = 0
            for j in range(-half, half + 1):
                a = age + j
                if 0 <= a < filled:
                    acc   += self._buf_get(self._samples, a)
                    count += 1
            sig[i] = acc // count if count else 0

        # DC removal: subtract integer mean
        total = 0
        for i in range(sig_len):
            total += sig[i]
        mean = total // sig_len
        for i in range(sig_len):
            sig[i] -= mean

        # Dynamic threshold at 30% of positive peak
        max_val = 0
        for i in range(sig_len):
            if sig[i] > max_val:
                max_val = sig[i]
        threshold = (max_val * 3) // 10

        # Peak detection with refractory period
        peaks_ts     = []
        last_peak_ts = ts[0] - _HR_MIN_PEAK_MS * 2  # allow first peak

        for i in range(1, sig_len - 1):
            if (sig[i] > threshold
                    and sig[i] > sig[i - 1]
                    and sig[i] > sig[i + 1]):
                t = ts[i]
                if ticks_diff(t, last_peak_ts) >= _HR_MIN_PEAK_MS:
                    peaks_ts.append(t)
                    last_peak_ts = t

        if len(peaks_ts) < 2:
            if self._bpm_count == 0:
                return None
            n = min(self._bpm_count, _HR_BPM_BUFFER_SIZE)
            return self._median(self._bpm_buf, n)

        # Intervals → BPM with physiological clamping
        for i in range(1, len(peaks_ts)):
            interval = ticks_diff(peaks_ts[i], peaks_ts[i - 1])
            if interval <= 0:
                continue
            bpm = 6000000 // interval // 100
            if _HR_MIN_BPM <= bpm <= _HR_MAX_BPM:
                idx = self._bpm_count % _HR_BPM_BUFFER_SIZE
                self._bpm_buf[idx] = bpm
                self._bpm_count += 1

        if self._bpm_count == 0:
            return None
        n = min(self._bpm_count, _HR_BPM_BUFFER_SIZE)
        return self._median(self._bpm_buf, n)


class HeartVitalsDisplay:
    """Integrates MAX30102 sensor and SH1106 display into a single update loop."""

    def __init__(self, sensor, display):
        self._sensor  = sensor
        self._display = display

        # Pre-allocated buffers
        self._wav_raw      = array('l', [0] * _DISP_W)   # raw IR ring for normalisation
        self._wav_y        = bytearray(_DISP_W)           # normalised waveform y-coords
        self._ir_avg_buf   = array('l', [0] * _IR_AVG_WINDOW)
        self._spo2_ir_buf  = array('l', [0] * _SPO2_WINDOW)
        self._spo2_red_buf = array('l', [0] * _SPO2_WINDOW)

        # Ring indices / counters
        self._wav_idx      = 0
        self._ir_avg_idx   = 0
        self._ir_avg_sum   = 0
        self._ir_avg_count = 0
        self._spo2_idx     = 0
        self._spo2_count   = 0

        # Waveform normalisation state
        self._wav_raw_min = 0x7FFFFFFF
        self._wav_raw_max = 0
        self._norm_ctr    = 0

        # Vitals state
        self._bpm     = None
        self._spo2    = None
        self._finger  = False
        self._quality = 0

        # Timing references
        now = ticks_ms()
        self._last_compute_ms = now
        self._last_draw_ms    = now
        self._beat_ref_ms     = now

        self._hr = _HRAlgorithm()

        # Initialise waveform to centre line
        centre = _WAV_H // 2
        for i in range(_DISP_W):
            self._wav_y[i] = centre

    # ------------------------------------------------------------------ #

    def update(self):
        """Call this in the main loop on every iteration."""
        self._poll_sensor()
        now = ticks_ms()
        if ticks_diff(now, self._last_draw_ms) >= _DRAW_INTERVAL_MS:
            self._draw()
            self._last_draw_ms = now
        if ticks_diff(now, self._last_compute_ms) >= _COMPUTE_INTERVAL_MS:
            self._compute_vitals()
            self._last_compute_ms = now

    # ------------------------------------------------------------------ #

    def _poll_sensor(self):
        sensor = self._sensor
        sensor.check()

        while sensor.available():
            ir  = sensor.pop_ir_from_storage()
            red = sensor.pop_red_from_storage()

            # Running average for finger detection
            old = self._ir_avg_buf[self._ir_avg_idx]
            self._ir_avg_buf[self._ir_avg_idx] = ir
            self._ir_avg_sum  += ir - old
            self._ir_avg_idx   = (self._ir_avg_idx + 1) % _IR_AVG_WINDOW
            if self._ir_avg_count < _IR_AVG_WINDOW:
                self._ir_avg_count += 1

            if self._ir_avg_count >= _IR_AVG_WINDOW:
                finger_now = (self._ir_avg_sum // _IR_AVG_WINDOW) >= _IR_FINGER_THRESHOLD
            else:
                finger_now = ir >= _IR_FINGER_THRESHOLD

            if self._finger and not finger_now:
                # Finger removed — reset all state
                self._finger     = False
                self._bpm        = None
                self._spo2       = None
                self._spo2_count = 0
                self._spo2_idx   = 0
                self._hr.reset()

                # Clear IR average so re-placement detection starts fresh
                for i in range(_IR_AVG_WINDOW):
                    self._ir_avg_buf[i] = 0
                self._ir_avg_sum   = 0
                self._ir_avg_count = 0

                # Reset waveform normalisation and flatten display
                self._wav_raw_min = 0x7FFFFFFF
                self._wav_raw_max = 0
                for i in range(_DISP_W):
                    self._wav_raw[i] = 0
                centre = _WAV_H // 2
                for i in range(_DISP_W):
                    self._wav_y[i] = centre

            elif not self._finger and finger_now:
                self._finger = True

            if self._finger:
                self._hr.add_sample(ir)
                self._spo2_ir_buf[self._spo2_idx]  = ir
                self._spo2_red_buf[self._spo2_idx] = red
                self._spo2_idx = (self._spo2_idx + 1) % _SPO2_WINDOW
                if self._spo2_count < _SPO2_WINDOW:
                    self._spo2_count += 1

            self._push_waveform(ir if self._finger else 0)

    # ------------------------------------------------------------------ #

    def _push_waveform(self, ir_val):
        idx = self._wav_idx
        self._wav_raw[idx] = ir_val
        self._wav_idx = (idx + 1) % _DISP_W

        # Incremental min/max update
        if ir_val > self._wav_raw_max:
            self._wav_raw_max = ir_val
        if ir_val < self._wav_raw_min:
            self._wav_raw_min = ir_val

        # Periodic full recompute to evict stale extremes after amplitude changes
        self._norm_ctr += 1
        if self._norm_ctr >= _NORM_RECOMPUTE_INTERVAL:
            self._norm_ctr = 0
            mn = 0x7FFFFFFF
            mx = 0
            for v in self._wav_raw:
                if v < mn: mn = v
                if v > mx: mx = v
            self._wav_raw_min = mn
            self._wav_raw_max = mx

        rng = self._wav_raw_max - self._wav_raw_min
        if rng == 0:
            y_norm = _WAV_H // 2
            self._quality = 0
        else:
            y_norm = ((ir_val - self._wav_raw_min) * (_WAV_H - 1)) // rng
            if y_norm < 0:
                y_norm = 0
            elif y_norm > _WAV_H - 1:
                y_norm = _WAV_H - 1
            if self._wav_raw_max > 0:
                self._quality = min((rng * 10 * 100) // self._wav_raw_max, 100)
            else:
                self._quality = 0

        self._wav_y[idx] = y_norm

    # ------------------------------------------------------------------ #

    def _compute_vitals(self):
        self._bpm = self._hr.calculate_heart_rate()
        self._compute_spo2()

    def _compute_spo2(self):
        n = self._spo2_count
        if n < 4:
            self._spo2 = None
            return

        ir_buf  = self._spo2_ir_buf
        red_buf = self._spo2_red_buf

        ir_sum  = 0
        red_sum = 0
        ir_min  = ir_buf[0];   ir_max  = ir_buf[0]
        red_min = red_buf[0];  red_max = red_buf[0]
        for i in range(n):
            iv = ir_buf[i];  rv = red_buf[i]
            ir_sum  += iv;   red_sum += rv
            if iv < ir_min:  ir_min  = iv
            if iv > ir_max:  ir_max  = iv
            if rv < red_min: red_min = rv
            if rv > red_max: red_max = rv

        dc_ir  = ir_sum  // n
        dc_red = red_sum // n
        ac_ir  = ir_max  - ir_min
        ac_red = red_max - red_min

        # Right-shift by 3 to keep products within int32 range
        dc_ir_s  = dc_ir  >> 3
        dc_red_s = dc_red >> 3
        ac_ir_s  = ac_ir  >> 3

        if dc_ir_s == 0 or dc_red_s == 0 or ac_ir_s == 0:
            self._spo2 = None
            return

        R_x1000 = (ac_red >> 3) * dc_ir_s * 1000 // (dc_red_s * ac_ir_s)
        spo2 = 104 - (17 * R_x1000) // 1000
        if spo2 < 80:  spo2 = 80
        if spo2 > 100: spo2 = 100
        self._spo2 = spo2

    # ------------------------------------------------------------------ #

    def _draw(self):
        display = self._display
        display.fill(0)

        if not self._finger:
            display.text("Place finger on", 4, 24)
            display.text("the sensor", 24, 32)
        else:
            # Heart animation (large for first 1/4 of beat cycle, small otherwise)
            now     = ticks_ms()
            beat_ms = (60000 // self._bpm) if self._bpm else 600
            elapsed = ticks_diff(now, self._beat_ref_ms)
            if elapsed >= beat_ms:
                self._beat_ref_ms = now
                elapsed = 0
            heart_bmp = _HEART_LARGE if elapsed < (beat_ms // 4) else _HEART_SMALL
            display.draw_bitmap(0, 0, heart_bmp, 8, 8)

            # BPM and SpO2 text (6 chars each = 48px each)
            bpm_str  = ("HR:{:3d}".format(self._bpm)   if self._bpm  is not None
                        else "HR:---")
            spo2_str = ("O2:{:2d}%".format(self._spo2) if self._spo2 is not None
                        else "O2:--%")
            display.text(bpm_str,  9, 0)
            display.text(spo2_str, 57, 0)

            # Quality bar: 22px outline at x=106, 20px usable fill
            display.rect(106, 0, 22, 8, 1)
            fill_w = self._quality * 20 // 100
            if fill_w > 0:
                display.fill_rect(107, 1, fill_w, 6, 1)

            # Separator
            display.hline(0, 8, 128, 1)

            # Waveform (y=9..63): connect consecutive samples with vline
            wav    = self._wav_y
            prev_y = 63 - wav[0]
            for x in range(1, _DISP_W):
                cur_y = 63 - wav[x]
                if cur_y == prev_y:
                    display.pixel(x, cur_y, 1)
                else:
                    y0 = cur_y  if cur_y  < prev_y else prev_y
                    h  = (prev_y - cur_y) if prev_y > cur_y else (cur_y - prev_y)
                    display.vline(x, y0, h + 1, 1)
                prev_y = cur_y

        display.show()
