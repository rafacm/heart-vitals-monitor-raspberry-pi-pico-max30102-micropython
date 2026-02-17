# Finger Detection for MAX30102

## Problem

The heart rate monitor had no way to distinguish between a finger being on the sensor and ambient noise. Without finger detection, the algorithm processed noise as valid signal data, producing meaningless BPM values. Users had no feedback about whether to place or reposition their finger.

## Changes

### `lib/max30102/__init__.py` — `check_finger()` method

Added a `check_finger(threshold=10000)` method to `MAX30102`. It calls `check()` to poll the sensor FIFO, pops the latest IR reading, and returns `True` if the value exceeds the threshold.

### `test/max30102_test.py` — Finger detection loop and `reset()`

- Added `HeartRateMonitor.reset()` to zero out all internal ring buffers (`_samples`, `_timestamps`, smoothing state, BPM buffer), enabling a clean start after finger removal.
- Restructured `main()` into a two-phase loop:
  1. **Waiting phase** — polls `sensor.check_finger()` until a finger is detected.
  2. **Reading phase** — collects samples, tracks a running IR average over 20 samples, and breaks back to the waiting phase when the average drops below the threshold.

## Key Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| IR finger threshold | 10,000 | Ambient/no-finger reads ~0–1,000; finger-on reads ~50,000–150,000. 10k provides clear margin. |
| Running average window | 20 samples | ~0.4 s at 50 Hz — fast enough to detect removal, smooth enough to avoid glitches. |

## Verification

```bash
mpremote cp -r lib/ :lib/ + cp test/max30102_test.py :test/max30102_test.py + run test/max30102_test.py
```

1. On boot: prints "Place your finger on the sensor..."
2. When finger placed: prints "Finger detected!" and begins heart rate computation.
3. During reading: prints BPM every 2 seconds.
4. When finger removed: prints "Finger removed", resets monitor, returns to step 1.

## Files Modified

| File | Change |
|------|--------|
| `lib/max30102/__init__.py` | Added `check_finger(threshold)` method to `MAX30102` class |
| `test/max30102_test.py` | Added `reset()` to `HeartRateMonitor`; restructured `main()` with finger detection and removal detection |
| `doc/features/finger-detection.md` | This document |
