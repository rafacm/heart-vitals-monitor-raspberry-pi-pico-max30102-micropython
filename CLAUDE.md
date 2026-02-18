# Heart Vitals

MicroPython heart-rate monitor running on a **Raspberry Pi Pico 2**. Reads pulse-oximetry and heart rate data from a MAX30102 sensor and displays output on an SH1106 OLED screen.

## Hardware

Each device uses a separate I2C bus:

| Bus  | Signal | Pin  | Device            |
|------|--------|------|-------------------|
| I2C1 | SDA    | GP18 | MAX30102          |
| I2C1 | SCL    | GP19 | MAX30102          |
| I2C0 | SDA    | GP12 | SH1106            |
| I2C0 | SCL    | GP13 | SH1106            |

| Device   | Bus  | I2C Address | Notes |
|----------|------|-------------|-------|
| MAX30102 | I2C1 | 0x57        | Pulse-oximeter / heart-rate sensor |
| SH1106   | I2C0 | 0x3C        | 128×64 OLED display |

Both buses run at 400 kHz.

## Project layout

```
main.py                        # Entry point (runs on boot)
lib/
  max30102.py                  # MAX30102 driver (I2C register access, FIFO reads)
  sh1106.py                   # SH1106 OLED driver (I2C, framebuf-based)
test/
  max30102_test.py             # On-device hardware check + heart-rate demo
  sh1106_test.py               # On-device display test suite (DisplayTester class)
doc/
  features/                    # Per-feature documentation (see Documentation section)
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
- The MAX30102 driver is a lean flat module (`lib/max30102.py`), originally based on the [n-elia MicroPython port](https://github.com/n-elia/MAX30102-MicroPython-driver) of the SparkFun library.

## Documentation

Feature documentation lives in `doc/features/`, one Markdown file per feature or significant change. Each document should include:

- **Problem** — what was wrong or what need the feature addresses.
- **Changes** — what was modified, with enough detail that a reader can understand the approach without reading the diff.
- **Key parameters** — any tunable constants, their values, and why those values were chosen.
- **Verification** — how to test the change on-device (deploy command + expected behaviour).
- **Files modified** — list of touched files with a one-line summary of each change.

Keep prose concise. Prefer tables and lists over long paragraphs. Use code blocks for CLI commands and signal-flow diagrams.
Add an entry for each feature or fix in the `doc/features/README.md` file.