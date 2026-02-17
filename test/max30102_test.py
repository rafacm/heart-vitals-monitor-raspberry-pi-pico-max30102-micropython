# Adapted from https://github.com/n-elia/MAX30102-MicroPython-driver/blob/main/examples/heart_rate/main.py
# I2C Configuration:
#   - SDA: GP12
#   - SCL: GP13
#   - Address: 0x57

import time
from machine import I2C, Pin
from utime import ticks_diff, ticks_ms

from max30102 import MAX30102, MAX30105_PULSE_AMP_MEDIUM


class HeartRateMonitor:
    """Heart rate monitor with DC removal, refractory period, physiological
    clamping, and median output filtering."""

    MIN_BPM = 40
    MAX_BPM = 200
    # Minimum ms between peaks (refractory period) — caps detection at ~200 BPM
    MIN_PEAK_DISTANCE_MS = 300

    def __init__(self, sample_rate=50, window_size=250, smoothing_window=15,
                 bpm_buffer_size=5):
        self.sample_rate = sample_rate
        self.window_size = window_size
        self.smoothing_window = smoothing_window
        self.bpm_buffer_size = bpm_buffer_size

        # Pre-allocated fixed-size ring buffers
        self._samples = [0] * window_size
        self._timestamps = [0] * window_size
        self._n = 0  # total samples added (head index = _n % window_size)

        # Smoothing accumulator
        self._smooth_buf = [0] * smoothing_window
        self._smooth_idx = 0
        self._smooth_sum = 0
        self._smooth_count = 0

        # BPM median buffer
        self._bpm_buf = [0.0] * bpm_buffer_size
        self._bpm_count = 0

    # ---- helpers ----

    @staticmethod
    def _median(lst, n):
        """Return median of the first *n* elements of *lst*."""
        tmp = sorted(lst[:n])
        mid = n // 2
        if n % 2 == 1:
            return tmp[mid]
        return (tmp[mid - 1] + tmp[mid]) / 2

    def _buf_get(self, buf, age):
        """Get an item from a ring buffer by age (0 = newest)."""
        idx = (self._n - 1 - age) % self.window_size
        return buf[idx]

    # ---- public API ----

    def reset(self):
        """Clear all internal buffers for a fresh reading session."""
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

        # Update running sum for smoothing window
        old = self._smooth_buf[self._smooth_idx]
        self._smooth_buf[self._smooth_idx] = sample
        self._smooth_sum += sample - old
        self._smooth_idx = (self._smooth_idx + 1) % self.smoothing_window
        if self._smooth_count < self.smoothing_window:
            self._smooth_count += 1

    def calculate_heart_rate(self):
        """Return the median-filtered BPM, or None if not enough data."""
        filled = min(self._n, self.window_size)
        if filled < self.smoothing_window + 2:
            return None

        # --- build DC-removed smoothed signal over the filled window ---
        sig_len = filled
        sig = [0] * sig_len  # smoothed & DC-removed
        ts = [0] * sig_len   # corresponding timestamps

        # We iterate from oldest to newest
        for i in range(sig_len):
            age = sig_len - 1 - i
            ts[i] = self._buf_get(self._timestamps, age)

            # Compute local moving-average centred on this sample
            half = self.smoothing_window // 2
            acc = 0
            count = 0
            for j in range(-half, half + 1):
                a = age + j
                if 0 <= a < filled:
                    acc += self._buf_get(self._samples, a)
                    count += 1
            sig[i] = acc / count if count else 0

        # DC removal: subtract overall mean
        mean = sum(sig) / sig_len
        for i in range(sig_len):
            sig[i] -= mean

        # --- peak detection with refractory period ---
        # Dynamic threshold at 30% of positive range
        max_val = max(sig)
        threshold = max_val * 0.3 if max_val > 0 else 0

        peaks_ts = []
        last_peak_ts = -self.MIN_PEAK_DISTANCE_MS * 2  # allow first peak

        for i in range(1, sig_len - 1):
            if (sig[i] > threshold
                    and sig[i] > sig[i - 1]
                    and sig[i] > sig[i + 1]):
                t = ts[i]
                if ticks_diff(t, last_peak_ts) >= self.MIN_PEAK_DISTANCE_MS:
                    peaks_ts.append(t)
                    last_peak_ts = t

        if len(peaks_ts) < 2:
            return None

        # --- intervals → BPM with physiological clamping ---
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


def main():
    # I2C instance
    i2c = I2C(
        sda=Pin(12),  # Here, use your I2C SDA pin
        scl=Pin(13),  # Here, use your I2C SCL pin
        freq=400000,
    )  # Fast: 400kHz, slow: 100kHz

    # Sensor instance
    sensor = MAX30102(i2c=i2c)  # An I2C instance is required

    # Scan I2C bus to ensure that the sensor is connected
    if sensor.i2c_address not in i2c.scan():
        print("Sensor not found.")
        return
    elif not (sensor.check_part_id()):
        # Check that the targeted sensor is compatible
        print("I2C device ID not corresponding to MAX30102 or MAX30105.")
        return
    else:
        print("Sensor connected and recognized.")

    # Load the default configuration
    print("Setting up sensor with default configuration.", "\n")
    sensor.setup_sensor()

    # Set the sample rate to 400: 400 samples/s are collected by the sensor
    sensor_sample_rate = 400
    sensor.set_sample_rate(sensor_sample_rate)

    # Set the number of samples to be averaged per each reading
    sensor_fifo_average = 8
    sensor.set_fifo_average(sensor_fifo_average)

    # Set LED brightness to a medium value
    sensor.set_active_leds_amplitude(MAX30105_PULSE_AMP_MEDIUM)

    # Expected acquisition rate: 400 Hz / 8 = 50 Hz
    actual_acquisition_rate = int(sensor_sample_rate / sensor_fifo_average)

    time.sleep(1)

    # IR threshold for finger detection
    IR_FINGER_THRESHOLD = 10000
    # Running average window for mid-reading finger removal detection
    IR_AVG_WINDOW = 20

    # Initialize the heart rate monitor with a 5-second window
    hr_monitor = HeartRateMonitor(
        sample_rate=actual_acquisition_rate,
        window_size=int(actual_acquisition_rate * 5),
        smoothing_window=15,
        bpm_buffer_size=5,
    )

    while True:
        # --- Wait for finger placement ---
        print("Place your finger on the sensor...")
        while not sensor.check_finger(IR_FINGER_THRESHOLD):
            time.sleep_ms(20)

        print("Finger detected! Starting heart rate measurement...\n")
        hr_monitor.reset()

        # Running average for finger removal detection
        ir_avg_sum = 0
        ir_avg_count = 0
        ir_avg_buf = [0] * IR_AVG_WINDOW
        ir_avg_idx = 0

        # Calculate the heart rate every 2 seconds
        hr_compute_interval = 2  # seconds
        ref_time = ticks_ms()
        finger_present = True

        while finger_present:
            sensor.check()

            if sensor.available():
                red_reading = sensor.pop_red_from_storage()
                ir_reading = sensor.pop_ir_from_storage()

                # Update running average for finger detection
                old = ir_avg_buf[ir_avg_idx]
                ir_avg_buf[ir_avg_idx] = ir_reading
                ir_avg_sum += ir_reading - old
                ir_avg_idx = (ir_avg_idx + 1) % IR_AVG_WINDOW
                if ir_avg_count < IR_AVG_WINDOW:
                    ir_avg_count += 1

                # Check for finger removal once we have enough samples
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


if __name__ == "__main__":
    main()
