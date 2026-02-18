# MAX30102 Driver Rewrite

## Problem

The original MAX30102 driver (`lib/max30102/__init__.py`, 710 lines) was adapted from the SparkFun/n-elia library and carried significant dead weight:

- 80+ methods, most unused by any caller in the project
- A separate `circular_buffer.py` module using `ucollections.deque`
- Verbose if/elif validation chains for every configuration parameter
- Mixed naming conventions (`camelCase`, `snake_case`, `UPPER_CASE` for locals)
- `ustruct.unpack` for FIFO decoding with per-sample byte-object allocation
- A `SensorData` class with a green channel buffer never read by any caller

## Changes

Replaced the `lib/max30102/` package (two files) with a single flat module `lib/max30102.py` (~170 lines).

| Aspect | Before | After |
|--------|--------|-------|
| Structure | Package (`__init__.py` + `circular_buffer.py`) | Single flat module |
| Lines | ~750 total | ~170 |
| Public methods | 80+ | 11 |
| Buffering | `CircularBuffer` class using `ucollections.deque` | Two pre-allocated `array('l')` ring buffers with head/tail integers |
| Config validation | if/elif chains per parameter | Lookup dicts (`_SAMPLE_AVG`, `_SAMPLE_RATE`, etc.) |
| FIFO decoding | `ustruct.unpack(">i", ...)` | Direct bit shifting `(b[0] << 16 \| b[1] << 8 \| b[2]) & 0x3FFFF` |
| Imports | `ustruct`, `ucollections`, `SoftI2C` | `array`, `utime.sleep_ms` only |
| Green channel | Buffered but never read | Removed |

### Public API preserved

All methods used by `main.py` and `heart_vitals_display.py` are preserved with identical signatures:

- `setup_sensor()`, `shutdown()`, `soft_reset()`
- `check()`, `available()`, `pop_ir_from_storage()`, `pop_red_from_storage()`
- `check_part_id()`, `read_temperature()`, `check_finger()`

### Caller updates

- `main.py`: Import changed from `MAX30105_PULSE_AMP_MEDIUM` to `LED_AMP_MEDIUM`
- `lib/heart_vitals_display.py`: No changes needed

### Test file

Replaced `test/max30102_test.py` with two entry points:

1. **`hardware_check()`** — I2C scan, part ID validation, temperature read, sample read
2. **`heart_rate_demo()`** — Finger detection loop with `HeartRateMonitor` class, BPM output every 2 s

## Key parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| Ring buffer size | 16 samples | Enough for burst reads at 50 Hz effective rate |
| LED amplitude presets | `LED_AMP_LOWEST` (0x02) through `LED_AMP_HIGH` (0xFF) | Same values as before, renamed for consistency |

## Verification

```bash
# Deploy and run hardware check + heart rate demo
mpremote cp -r lib/ :lib/ + cp test/max30102_test.py :test/max30102_test.py + run test/max30102_test.py

# Deploy and run main application
mpremote cp -r lib/ :lib/ + cp main.py :main.py + run main.py
```

Expected: `hardware_check()` prints PASS for part ID, a plausible die temperature (20–40 C), and at least one sample. `heart_rate_demo()` detects finger and prints BPM. Main app shows live waveform on OLED.

## Files modified

| File | Change |
|------|--------|
| `lib/max30102/` (deleted) | Removed entire package directory |
| `lib/max30102.py` (new) | Clean-slate flat driver module |
| `main.py` | Updated import to `LED_AMP_MEDIUM` |
| `test/max30102_test.py` | Rewritten with `hardware_check()` + `heart_rate_demo()` |
| `README.md` | Updated project layout; added "How the MAX30102 sensor works" section |
| `CLAUDE.md` | Updated project layout |
| `doc/features/README.md` | Added entry for this rewrite |
