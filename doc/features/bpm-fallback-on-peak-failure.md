# BPM Fallback on Peak Detection Failure

## Problem

During continuous heart rate measurement, intermittent "Not enough data to calculate heart rate" messages appeared even with a finger firmly on the sensor. The peak detection algorithm occasionally fails to find >= 2 peaks in the current 5-second analysis window (e.g. due to motion artefacts or signal amplitude changes). When this happened, `calculate_heart_rate()` returned `None` immediately — discarding valid BPM readings already accumulated in the median buffer from previous windows.

## Changes

### `test/max30102_test.py` — `HeartRateMonitor.calculate_heart_rate()`

When peak detection finds fewer than 2 peaks, the method now checks whether previous BPM readings exist in `_bpm_buf`. If they do, it returns the median of those existing readings instead of `None`. The method only returns `None` during initial warmup, before any valid BPM has ever been recorded.

```python
# Before
if len(peaks_ts) < 2:
    return None

# After
if len(peaks_ts) < 2:
    if self._bpm_count == 0:
        return None
    n = min(self._bpm_count, self.bpm_buffer_size)
    return self._median(self._bpm_buf, n)
```

## Key parameters

No new parameters. The fix reuses the existing `_bpm_buf` (size 5) and `_bpm_count` accumulator.

## Verification

Deploy and run:

```bash
mpremote cp -r lib/ :lib/ + cp test/max30102_test.py :test/max30102_test.py + run test/max30102_test.py
```

Expected behaviour:
- "Not enough data" appears only during the first few seconds before any valid BPM is computed.
- Once a valid BPM is recorded, every subsequent 2-second interval reports a numeric BPM value.
- No gaps in output during continuous finger-on-sensor measurement.

## Files modified

- `test/max30102_test.py` — added fallback to last known median in `calculate_heart_rate()` when peak detection fails mid-session.
