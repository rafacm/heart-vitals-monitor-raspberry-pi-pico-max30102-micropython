# Heart Vitals

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Heart vitals monitor using Raspberry Pi Pico 2W, a MAX30102 heart rate sensor and a 128×64 OLED display, each connected to the Pico on a separate I2C bus.

## Hardware

Each device uses a dedicated I2C bus, both running at 400 kHz:

| Bus  | Signal | Pin  | Device   |
|------|--------|------|----------|
| I2C1 | SDA    | GP18 | MAX30102 |
| I2C1 | SCL    | GP19 | MAX30102 |
| I2C0 | SDA    | GP12 | SH1106   |
| I2C0 | SCL    | GP13 | SH1106   |

| Device   | Bus  | I2C Address | Notes |
|----------|------|-------------|-------|
| MAX30102 | I2C1 | 0x57        | Pulse-oximeter / heart-rate sensor |
| SH1106   | I2C0 | 0x3C        | 128×64 OLED display |

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

## Acknowledgements

- MAX30102 driver adapted from the [n-elia MicroPython port](https://github.com/n-elia/MAX30102-MicroPython-driver) of the SparkFun library.
- Built with assistance from [Claude](https://claude.ai).

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
