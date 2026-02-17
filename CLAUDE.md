# Heart Vitals

MicroPython heart-rate monitor running on a **Raspberry Pi Pico 2**. Reads pulse-oximetry and heart rate data from a MAX30102 sensor and displays output on an SH1106 OLED screen.

## Hardware

Both devices share a single I2C bus:

| Signal | Pin  |
|--------|------|
| SDA    | GP12 |
| SCL    | GP13 |

| Device   | I2C Address | Notes |
|----------|-------------|-------|
| MAX30102 | 0x57        | Pulse-oximeter / heart-rate sensor |
| SH1106   | 0x3C        | 128×64 OLED display |

I2C runs at 400 kHz.

## Project layout

```
main.py                        # Entry point (runs on boot)
lib/
  max30102/
    __init__.py                # MAX30102 driver (I2C register access, FIFO reads)
    circular_buffer.py         # Ring buffer backed by ucollections.deque
  sh1106.py                   # SH1106 OLED driver (I2C, framebuf-based)
test/
  max30102_test.py             # On-device heart-rate demo (HeartRateMonitor class)
  sh1106_test.py               # On-device display test suite (DisplayTester class)
```

## Deploying to the board

Use `mpremote` (install with `pip install mpremote`):

```bash
# Copy entire project to the board
mpremote cp -r lib/ :lib/
mpremote cp main.py :main.py

# Copy and run a test file
mpremote cp -r lib/ :lib/ + cp test/max30102_test.py :test/max30102_test.py + run test/max30102_test.py
```

## Running tests

Tests run directly on the Pico — there is no host-side test harness. Connect the board via USB and:

```bash
mpremote run test/max30102_test.py   # Heart-rate acquisition test
mpremote run test/sh1106_test.py     # OLED display test suite
```

Both test files have a `main()` entry point guarded by `if __name__ == "__main__"`.

## Conventions

- **MicroPython built-ins only** — no pip packages, no external dependencies. Use `machine`, `framebuf`, `ustruct`, `ucollections`, `utime`, etc.
- Drivers live under `lib/` so MicroPython's import path finds them automatically.
- Code must fit in the Pico 2W's constrained RAM — keep allocations small, prefer pre-allocated buffers.
- The MAX30102 driver is adapted from the [n-elia MicroPython port](https://github.com/n-elia/MAX30102-MicroPython-driver) of the SparkFun library.
