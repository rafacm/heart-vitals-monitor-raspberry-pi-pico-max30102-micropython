# Display Redesign — Three-Row Layout

## Problem

The original display layout crammed all information into a single 8px header row (8×8 heart, HR text, SpO2 text, quality bar) with the remaining 55px used for the waveform. The heart icon was too small, vitals were hard to read, and there was no elapsed-time indicator. The waveform also drew samples in ring-buffer order rather than scrolling naturally.

## Changes

Replaced the single-row header with a structured three-row layout on the 128×64 OLED:

```
y=0–15   [Row 1] 16×16 heart (beat animation) | BPM + SpO2 text
y=16     ─────────── separator ───────────────
y=17–54  [Row 2] Waveform (38px tall, scrolls right-to-left)
y=55     ─────────── separator ───────────────
y=56–63  [Row 3] Elapsed time | Quality bar
```

### Header (y=0–15)

- 16×16 heart bitmap replaces the old 8×8 version; two bitmaps for beat animation (large/small).
- BPM displayed on y=0, SpO2 on y=8, both starting at x=18 (right of the heart).

### Waveform (y=17–54)

- Right-to-left scrolling: newest sample appears at x=127, oldest at x=0.
- Ring buffer read order changed in `_draw()` to `(wav_idx + x) % 128` (oldest → newest maps to left → right).
- `_push_waveform()` write logic unchanged.

### Status bar (y=56–63)

- Left side: elapsed seconds since finger placement (`{:3d}s` format).
- Right side: quality bar — 94px outlined rectangle with proportional fill (max 92px inner width).

### Finger placement timer

- `_finger_start_ms` tracks when the finger was first detected.
- Set on the `not finger → finger` transition; reset to 0 on finger removal.

## Key parameters

| Constant | Value | Reason |
|----------|-------|--------|
| `_WAV_TOP` | 17 | Below 16px header + 1px separator |
| `_WAV_H` | 38 | y=17..54 (38 pixels) |
| `_STATUS_Y` | 56 | Below lower separator at y=55 |
| `_HEART_SIZE` | 16 | 16×16 bitmap dimension |

## Verification

```bash
mpremote cp -r lib/ :lib/ + run main.py
```

1. **No finger:** Display shows "Place finger on / the sensor" centred vertically.
2. **Finger on:** Header shows 16×16 beating heart + BPM + SpO2; waveform scrolls left with new data appearing at the right edge; status bar shows elapsed seconds and quality fill bar.
3. **Finger removed:** Display returns to prompt; timer resets; waveform flattens.

## Files modified

| File | Summary |
|------|---------|
| `lib/heart_vitals_display.py` | Updated constants, replaced 8×8 bitmaps with 16×16, added `_finger_start_ms` state, rewrote `_draw()` for three-row layout with right-to-left waveform scrolling, updated `_poll_sensor()` for finger timing |
