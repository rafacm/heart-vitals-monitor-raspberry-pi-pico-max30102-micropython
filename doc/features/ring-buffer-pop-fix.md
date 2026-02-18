# Ring Buffer Pop Fix

## Problem

The heart-rate demo detected a finger but immediately reported "Finger removed" in a tight loop, even with a finger firmly on the sensor. No BPM readings were ever produced.

Root cause: `pop_red_from_storage()` and `pop_ir_from_storage()` each independently advance the shared `_tail` pointer. The ring buffer stores both red and IR at the same index, so calling both in sequence:

```python
red = sensor.pop_red_from_storage()   # reads red[tail], tail → tail+1
ir  = sensor.pop_ir_from_storage()    # reads ir[tail+1], tail → tail+2
```

This caused two problems:

1. **Misaligned channels** — red and IR readings came from different FIFO samples.
2. **2x drain rate** — the 16-slot ring buffer emptied twice as fast as expected. When empty, `pop_ir_from_storage()` returns 0, dragging the IR moving average below the finger threshold and triggering "Finger removed."

## Changes

| File | Change |
|------|--------|
| `lib/max30102.py` | Added `pop_sample()` method that returns `(red, ir)` from the same slot with a single tail advance. |
| `test/max30102_test.py` | Updated `hardware_check()` and `heart_rate_demo()` to use `pop_sample()` instead of separate pop calls. |

## Key parameters

No new parameters. The existing `_BUF_SIZE = 16` ring buffer is unchanged.

## Verification

```bash
mpremote cp lib/max30102.py :lib/ + cp test/max30102_test.py :test/ + run test/max30102_test.py
```

Expected behaviour:

- Hardware check prints paired IR/RED values from the same FIFO sample.
- Heart-rate demo sustains finger detection while a finger is on the sensor.
- BPM readings appear every 2 seconds after sufficient data is collected.

## Files modified

- `lib/max30102.py` — added `pop_sample()` returning `(red, ir)` from the same ring buffer slot.
- `test/max30102_test.py` — replaced separate `pop_red` / `pop_ir` calls with `pop_sample()`.
