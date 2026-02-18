import time
from machine import I2C, Pin
from utime import ticks_diff, ticks_ms

from max30102 import MAX30102, LED_AMP_MEDIUM


class HeartRateMonitor:
    """Heart rate monitor with DC removal, refractory period, physiological
    clamping, and median output filtering."""

    MIN_BPM = 40
    MAX_BPM = 200
    MIN_PEAK_DISTANCE_MS = 300

    def __init__(self, sample_rate=50, window_size=250, smoothing_window=15,
                 bpm_buffer_size=5):
        self.sample_rate = sample_rate
        self.window_size = window_size
        self.smoothing_window = smoothing_window
        self.bpm_buffer_size = bpm_buffer_size

        self._samples = [0] * window_size
        self._timestamps = [0] * window_size
        self._n = 0

        self._smooth_buf = [0] * smoothing_window
        self._smooth_idx = 0
        self._smooth_sum = 0
        self._smooth_count = 0

        self._bpm_buf = [0.0] * bpm_buffer_size
        self._bpm_count = 0

    @staticmethod
    def _median(lst, n):
        tmp = sorted(lst[:n])
        mid = n // 2
        if n % 2 == 1:
            return tmp[mid]
        return (tmp[mid - 1] + tmp[mid]) / 2

    def _buf_get(self, buf, age):
        return buf[(self._n - 1 - age) % self.window_size]

    def reset(self):
        for i in range(self.window_size):
            self._samples[i] = 0
            self._timestamps[i] = 0
        self._n = 0
        for i in range(self.smoothing_window):
            self._smooth_buf[i] = 0
        self._smooth_idx = 0
        self._smooth_sum = 0
        self._smooth_count = 0
        for i in range(self.bpm_buffer_size):
            self._bpm_buf[i] = 0.0
        self._bpm_count = 0

    def add_sample(self, sample):
        ts = ticks_ms()
        idx = self._n % self.window_size
        self._samples[idx] = sample
        self._timestamps[idx] = ts
        self._n += 1

        old = self._smooth_buf[self._smooth_idx]
        self._smooth_buf[self._smooth_idx] = sample
        self._smooth_sum += sample - old
        self._smooth_idx = (self._smooth_idx + 1) % self.smoothing_window
        if self._smooth_count < self.smoothing_window:
            self._smooth_count += 1

    def calculate_heart_rate(self):
        filled = min(self._n, self.window_size)
        if filled < self.smoothing_window + 2:
            return None

        sig_len = filled
        sig = [0] * sig_len
        ts = [0] * sig_len

        for i in range(sig_len):
            age = sig_len - 1 - i
            ts[i] = self._buf_get(self._timestamps, age)
            half = self.smoothing_window // 2
            acc = 0
            count = 0
            for j in range(-half, half + 1):
                a = age + j
                if 0 <= a < filled:
                    acc += self._buf_get(self._samples, a)
                    count += 1
            sig[i] = acc / count if count else 0

        mean = sum(sig) / sig_len
        for i in range(sig_len):
            sig[i] -= mean

        max_val = max(sig)
        threshold = max_val * 0.3 if max_val > 0 else 0

        peaks_ts = []
        last_peak_ts = -self.MIN_PEAK_DISTANCE_MS * 2

        for i in range(1, sig_len - 1):
            if (sig[i] > threshold
                    and sig[i] > sig[i - 1]
                    and sig[i] > sig[i + 1]):
                t = ts[i]
                if ticks_diff(t, last_peak_ts) >= self.MIN_PEAK_DISTANCE_MS:
                    peaks_ts.append(t)
                    last_peak_ts = t

        if len(peaks_ts) < 2:
            if self._bpm_count == 0:
                return None
            n = min(self._bpm_count, self.bpm_buffer_size)
            return self._median(self._bpm_buf, n)

        for i in range(1, len(peaks_ts)):
            interval = ticks_diff(peaks_ts[i], peaks_ts[i - 1])
            if interval <= 0:
                continue
            bpm = 60000 / interval
            if self.MIN_BPM <= bpm <= self.MAX_BPM:
                idx = self._bpm_count % self.bpm_buffer_size
                self._bpm_buf[idx] = bpm
                self._bpm_count += 1

        if self._bpm_count == 0:
            return None
        n = min(self._bpm_count, self.bpm_buffer_size)
        return self._median(self._bpm_buf, n)


def hardware_check():
    """Quick hardware validation: I2C scan, part ID, temperature, sample read."""
    print("=== MAX30102 Hardware Check ===\n")

    i2c = I2C(1, sda=Pin(18), scl=Pin(19), freq=400_000)

    devices = i2c.scan()
    print("I2C scan: {}".format(["0x{:02X}".format(d) for d in devices]))
    if 0x57 not in devices:
        print("FAIL: MAX30102 not found on I2C bus")
        return False

    sensor = MAX30102(i2c=i2c)

    ok = sensor.check_part_id()
    print("Part ID check: {}".format("PASS" if ok else "FAIL"))
    if not ok:
        return False

    temp = sensor.read_temperature()
    print("Die temperature: {:.2f} C".format(temp))

    sensor.setup_sensor()
    time.sleep_ms(500)
    sensor.check()
    n = sensor.available()
    print("Buffered samples after 500 ms: {}".format(n))
    if n > 0:
        red, ir = sensor.pop_sample()
        print("First sample — IR: {}, RED: {}".format(ir, red))

    sensor.shutdown()
    print("\nHardware check complete.\n")
    return True


def heart_rate_demo():
    """Finger detection loop with BPM output every 2 s."""
    print("=== Heart Rate Demo ===\n")

    i2c = I2C(1, sda=Pin(18), scl=Pin(19), freq=400_000)
    sensor = MAX30102(i2c=i2c)
    sensor.setup_sensor()

    sensor_sample_rate = 400
    sensor_fifo_average = 8
    actual_rate = sensor_sample_rate // sensor_fifo_average

    time.sleep(1)

    IR_FINGER_THRESHOLD = 10000
    IR_AVG_WINDOW = 20

    hr_monitor = HeartRateMonitor(
        sample_rate=actual_rate,
        window_size=actual_rate * 5,
        smoothing_window=15,
        bpm_buffer_size=5,
    )

    while True:
        print("Place your finger on the sensor...")
        while not sensor.check_finger(IR_FINGER_THRESHOLD):
            time.sleep_ms(20)

        print("Finger detected! Starting heart rate measurement...\n")
        hr_monitor.reset()

        ir_avg_sum = 0
        ir_avg_count = 0
        ir_avg_buf = [0] * IR_AVG_WINDOW
        ir_avg_idx = 0

        hr_compute_interval = 2
        ref_time = ticks_ms()
        finger_present = True

        while finger_present:
            sensor.check()

            if sensor.available():
                red_reading, ir_reading = sensor.pop_sample()

                old = ir_avg_buf[ir_avg_idx]
                ir_avg_buf[ir_avg_idx] = ir_reading
                ir_avg_sum += ir_reading - old
                ir_avg_idx = (ir_avg_idx + 1) % IR_AVG_WINDOW
                if ir_avg_count < IR_AVG_WINDOW:
                    ir_avg_count += 1

                if ir_avg_count >= IR_AVG_WINDOW:
                    ir_avg = ir_avg_sum / ir_avg_count
                    if ir_avg < IR_FINGER_THRESHOLD:
                        print("Finger removed.\n")
                        finger_present = False
                        break

                hr_monitor.add_sample(ir_reading)

            if ticks_diff(ticks_ms(), ref_time) / 1000 > hr_compute_interval:
                heart_rate = hr_monitor.calculate_heart_rate()
                if heart_rate is not None:
                    print("Heart Rate: {:.0f} BPM".format(heart_rate))
                else:
                    print("Not enough data to calculate heart rate")
                ref_time = ticks_ms()


def main():
    if hardware_check():
        heart_rate_demo()


if __name__ == "__main__":
    main()
