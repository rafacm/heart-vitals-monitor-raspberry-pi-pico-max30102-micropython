# Heart Vitals Display — Sensor + OLED Integration

## Problem

The project had working MAX30102 and SH1106 drivers but no top-level integration layer. The heart-rate algorithm lived inside `test/max30102_test.py` (not importable as a library), there was no SpO2 computation, no display output, and no `main.py` boot entry point. The device produced console output only and required a host computer attached.

## Changes

### `lib/heart_vitals_display.py` — new integration module

Self-contained module that owns the sense-compute-draw loop. Two classes:

**`_HRAlgorithm`** — integer-only port of `HeartRateMonitor` from `test/max30102_test.py`:
- All `list` ring buffers replaced with `array('l', …)` (pre-allocated signed-long arrays), saving ~8 KB of heap compared to Python lists.
- Floats eliminated throughout: moving-average smoothing uses integer accumulator division; DC removal uses integer mean (`total // n`); peak threshold uses `(max_val * 3) // 10`; BPM computed as `6_000_000 // interval_ms // 100`.
- Two extra `array('l', …)` working buffers (`_sig`, `_ts`, each 250 elements) are pre-allocated at init to avoid per-call heap allocation in `calculate_heart_rate()`.

**`HeartVitalsDisplay`** — the main integration class:

| Method | Cadence | Responsibility |
|---|---|---|
| `update()` | Every loop iteration | Drives the other three; checks timers |
| `_poll_sensor()` | Every iteration | Drains FIFO; finger detection; feeds HR algo and SpO2 buffers |
| `_draw()` | Every 300 ms | Renders "Place finger" or active vitals screen to OLED |
| `_compute_vitals()` | Every 2 s | Calls HR algorithm and SpO2 calculation |

**Finger detection** uses a 20-sample running IR average (same pattern as `test/max30102_test.py`). On removal, all state is cleared: HR algorithm buffers, SpO2 buffers, IR average, waveform ring, and min/max normalisation bounds.

**Waveform normalisation** maintains a 128-sample raw IR ring. Min/max are updated incrementally on every sample and fully recomputed every 256 samples to evict stale extremes after amplitude changes.

**SpO2 estimation** uses the R-ratio method (integer-only):
```
dc_ir, dc_red = means of 20-sample windows
ac_ir, ac_red = (max − min) of same windows
R_x1000 = (ac_red >> 3) × (dc_ir >> 3) × 1000 // ((dc_red >> 3) × (ac_ir >> 3))
SpO2    = clamp(104 − (17 × R_x1000) // 1000, 80, 100)
```
Inputs are right-shifted by 3 before multiplying to keep intermediate products below the int32 limit.

**Beating heart animation** uses two pre-computed 8×8 bitmaps:
- Large heart shown for the first ¼ of each beat cycle.
- Small heart shown for the remaining ¾.
- Beat period derived from live BPM; defaults to 600 ms (~100 BPM) until a reading is available.

**Display layout (active state):**
```
┌──────────────────────────────────────────────────────────────────┐
│ [♥] HR: 72  O2:98%                              [quality bar]    │  y=0–7
│──────────────────────────────────────────────────────────────────│  y=8
│                                                                  │
│                   scrolling IR waveform                          │  y=9–63
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### `main.py` — new boot entry point

Initialises both I2C buses, sensor, and display; configures the sensor; then enters a tight poll loop with no `sleep_ms`. The sensor's `check()` call is cheap (2 register reads); the display I2C transfer (every 300 ms, ~23 ms) accounts for ~7.7% CPU.

## Key Parameters

| Constant | Value | Rationale |
|---|---|---|
| `_DRAW_INTERVAL_MS` | 300 ms | Smooth waveform scroll without monopolising CPU |
| `_COMPUTE_INTERVAL_MS` | 2 000 ms | Matches original algorithm cadence; enough samples for stable median |
| `_NORM_RECOMPUTE_INTERVAL` | 256 samples | ~5 s at 50 Hz — periodic enough to correct stale min/max without being expensive |
| `_IR_FINGER_THRESHOLD` | 10 000 | Same proven value from finger-detection feature |
| `_IR_AVG_WINDOW` | 20 samples | ~0.4 s at 50 Hz — fast removal detection, smooth against glitches |
| `_SPO2_WINDOW` | 20 samples | Wide enough for stable AC/DC ratio, narrow enough to be fresh |
| `_WAV_H` | 55 px | y=9..63 (64 − 1 separator − 8 header rows) |
| `_HR_WINDOW_SIZE` | 250 samples | ~5 s at 50 Hz — covers several heartbeat cycles |
| `_HR_SMOOTHING_WINDOW` | 15 samples | ~0.3 s — removes high-frequency noise, preserves pulse shape |
| `_HR_BPM_BUFFER_SIZE` | 5 readings | Median of 5 suppresses single outlier intervals |

## Verification

```bash
mpremote cp -r lib/ :lib/ + cp main.py :main.py
mpremote run main.py
```

Expected behaviour:
1. Boot → OLED shows "Place finger on / the sensor" centred on screen.
2. Place finger → header row appears: beating heart icon (top-left), `HR: XX` and `O2:XX%` text, quality bar (top-right); waveform begins scrolling below separator.
3. Values populate within ~4–6 s; heart icon pulses at the measured BPM cadence.
4. Quality bar fills proportionally to the PPG AC/DC ratio.
5. Remove finger → vitals reset, "Place finger" message returns.

## Files Modified

| File | Change |
|---|---|
| `lib/heart_vitals_display.py` | New — integration module (`_HRAlgorithm` + `HeartVitalsDisplay`) |
| `main.py` | New — boot entry point |
| `doc/features/heart-vitals-display.md` | This document |
