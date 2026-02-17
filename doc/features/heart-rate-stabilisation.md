# Heart Rate Stabilisation

## Problem

The `HeartRateMonitor` in `test/max30102_test.py` produced wildly fluctuating BPM values (54-348 BPM). Root causes:

1. **Driver bug** — `check()` in the MAX30102 driver only read one FIFO sample per call, even when multiple were queued, starving the signal pipeline.
2. **Insufficient smoothing** — a 5-sample moving average (~100 ms at 50 Hz) was too short to suppress high-frequency noise.
3. **No DC removal** — peak detection used an absolute threshold that drifted with baseline changes.
4. **No refractory period** — noise spikes within the same heartbeat could register as separate peaks.
5. **No physiological filtering** — impossible BPM values (e.g. 348) were reported without question.
6. **No output stabilisation** — each reading was a single-shot calculation with no inter-reading smoothing.
7. **Growing Python lists** — `list.pop(0)` caused O(n) memory copies on every sample.

## Changes

### 1. FIFO drain fix (`lib/max30102/__init__.py`)

The `return True` statement on line 684 was inside the `for` loop that iterates over queued FIFO samples. This caused `check()` to return after reading only one sample, regardless of how many were available. The fix dedents `return True` one level so it executes after the loop completes, draining all queued samples in a single call.

### 2. HeartRateMonitor rewrite (`test/max30102_test.py`)

| Aspect | Before | After |
|--------|--------|-------|
| Smoothing window | 5 samples (~100 ms) | 15 samples (~300 ms) |
| Analysis window | 3 seconds (150 samples) | 5 seconds (250 samples) |
| DC removal | None | Subtract window mean from smoothed signal |
| Refractory period | None | 300 ms minimum between peaks (~200 BPM cap) |
| BPM range filter | None | Discard intervals outside 40-200 BPM |
| Output filter | None | Median of last 5 valid BPM values |
| Data structures | Growing Python lists with `pop(0)` | Pre-allocated fixed-size ring buffers |

#### Signal processing pipeline

```
Raw IR samples
    |
    v
Ring buffer (250 samples, ~5 s)
    |
    v
Moving-average smoothing (15-sample window)
    |
    v
DC removal (subtract overall mean)
    |
    v
Peak detection (local maxima above 30% of positive range)
    |
    v
Refractory filter (>= 300 ms between peaks)
    |
    v
Interval-to-BPM conversion
    |
    v
Physiological clamp (40-200 BPM)
    |
    v
Median filter (last 5 valid BPMs)
    |
    v
Displayed BPM
```

#### Key parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `smoothing_window` | 15 | ~300 ms at 50 Hz; suppresses noise without over-smoothing heartbeat peaks |
| `window_size` | 250 | 5 seconds at 50 Hz; captures 4-16 heartbeat cycles across the physiological range |
| `MIN_PEAK_DISTANCE_MS` | 300 | Prevents double-counting; corresponds to a 200 BPM ceiling |
| `MIN_BPM` / `MAX_BPM` | 40 / 200 | Standard physiological resting-to-exercise range |
| `bpm_buffer_size` | 5 | Odd-sized buffer for a clean median; smooths ~10 s of readings at 2 s intervals |

## Verification

Deploy to the Pico and run:

```bash
mpremote cp -r lib/ :lib/ + cp test/max30102_test.py :test/max30102_test.py + run test/max30102_test.py
```

Expected behaviour:
- BPM readings stabilise within ~10 seconds of placing a finger on the sensor.
- Steady-state readings stay within +/-5-10 BPM of actual heart rate.
- No readings outside 40-200 BPM are ever displayed.

## Files modified

- `lib/max30102/__init__.py` — moved `return True` outside `for` loop in `check()`
- `test/max30102_test.py` — rewrote `HeartRateMonitor` class and updated `main()` parameters
