"""
SH1106 OLED Display Test Suite for Raspberry Pi Pico 2W

Tests various display functions including:
- Basic text display
- Shapes (lines, rectangles, circles, triangles)
- Display control (contrast, invert, power)
- Scrolling
- Custom bitmaps

Hardware Setup:
- SDA: GP12
- SCL: GP13
- I2C Address: 0x3C
"""

import time
from machine import Pin, I2C
from sh1106 import SH1106


class DisplayTester:
    """Test class for SH1106 OLED display."""

    def __init__(self, i2c, addr=0x3C):
        """
        Initialize the display tester.

        Args:
            i2c: Initialized I2C bus (shared across all tests)
            addr: I2C address of the display
        """
        self.display = SH1106(i2c, addr=addr)
        self.width = self.display.width
        self.height = self.display.height

    def clear_and_wait(self, seconds=2):
        """Clear display and wait."""
        time.sleep(seconds)
        self.display.clear()

    def test_basic_text(self):
        """Test basic text display."""
        print("Test 1: Basic Text Display")
        self.display.fill(0)
        self.display.text("SH1106 OLED", 10, 0)
        self.display.text("128x64 pixels", 10, 12)
        self.display.text("MicroPython", 10, 24)
        self.display.text("Pico 2W", 10, 36)
        self.display.text("I2C: 0x3C", 10, 48)
        self.display.show()
        self.clear_and_wait()

    def test_pixels(self):
        """Test individual pixel control."""
        print("Test 2: Pixel Control")
        self.display.fill(0)

        # Draw a pattern of pixels
        for x in range(0, self.width, 4):
            for y in range(0, self.height, 4):
                self.display.pixel(x, y, 1)

        self.display.text("Pixel Test", 25, 28)
        self.display.show()
        self.clear_and_wait()

    def test_lines(self):
        """Test line drawing."""
        print("Test 3: Line Drawing")
        self.display.fill(0)

        # Diagonal lines
        self.display.line(0, 0, self.width - 1, self.height - 1, 1)
        self.display.line(0, self.height - 1, self.width - 1, 0, 1)

        # Horizontal and vertical lines
        self.display.hline(0, self.height // 2, self.width, 1)
        self.display.vline(self.width // 2, 0, self.height, 1)

        self.display.show()
        self.clear_and_wait()

    def test_rectangles(self):
        """Test rectangle drawing."""
        print("Test 4: Rectangle Drawing")
        self.display.fill(0)

        # Nested rectangles (outline)
        for i in range(0, 30, 5):
            self.display.rect(i, i, self.width - 2 * i, self.height - 2 * i, 1)

        self.display.show()
        time.sleep(2)

        # Filled rectangles
        self.display.fill(0)
        self.display.fill_rect(10, 10, 30, 20, 1)
        self.display.fill_rect(50, 10, 30, 20, 1)
        self.display.fill_rect(90, 10, 30, 20, 1)
        self.display.fill_rect(10, 35, 50, 25, 1)
        self.display.fill_rect(70, 35, 50, 25, 1)
        self.display.show()
        self.clear_and_wait()

    def test_circles(self):
        """Test circle drawing."""
        print("Test 5: Circle Drawing")
        self.display.fill(0)

        # Multiple circles
        self.display.circle(30, 32, 25, 1)
        self.display.circle(64, 32, 20, 1)
        self.display.circle(98, 32, 25, 1)

        self.display.show()
        time.sleep(2)

        # Filled circles
        self.display.fill(0)
        self.display.circle(32, 32, 20, 1, fill=True)
        self.display.circle(96, 32, 20, 1, fill=True)
        self.display.circle(64, 32, 15, 1, fill=True)
        self.display.show()
        self.clear_and_wait()

    def test_triangles(self):
        """Test triangle drawing."""
        print("Test 6: Triangle Drawing")
        self.display.fill(0)

        # Outline triangle
        self.display.triangle(10, 55, 50, 10, 90, 55, 1)

        # Filled triangle
        self.display.triangle(70, 55, 95, 10, 120, 55, 1, fill=True)

        self.display.show()
        self.clear_and_wait()

    def test_contrast(self):
        """Test contrast adjustment."""
        print("Test 7: Contrast Control")
        self.display.fill(0)
        self.display.text("Contrast Test", 15, 28)
        self.display.show()

        # Fade out
        for i in range(255, -1, -15):
            self.display.contrast(i)
            time.sleep(0.1)

        time.sleep(0.5)

        # Fade in
        for i in range(0, 256, 15):
            self.display.contrast(i)
            time.sleep(0.1)

        self.display.contrast(0xCF)  # Reset to default
        self.clear_and_wait()

    def test_invert(self):
        """Test display inversion."""
        print("Test 8: Display Inversion")
        self.display.fill(0)
        self.display.text("Invert Test", 20, 20)
        self.display.fill_rect(20, 35, 88, 20, 1)
        self.display.text("INVERTED", 28, 40, 0)
        self.display.show()

        for _ in range(4):
            time.sleep(0.5)
            self.display.invert(True)
            time.sleep(0.5)
            self.display.invert(False)

        self.clear_and_wait()

    def test_scroll(self):
        """Test display scrolling."""
        print("Test 9: Scrolling")
        self.display.fill(0)
        self.display.text("Scroll Test", 20, 28)
        self.display.show()
        time.sleep(1)

        # Scroll right
        for _ in range(64):
            self.display.scroll(2, 0)
            self.display.show()
            time.sleep(0.02)

        # Scroll down
        for _ in range(32):
            self.display.scroll(0, 2)
            self.display.show()
            time.sleep(0.02)

        self.clear_and_wait()

    def test_power(self):
        """Test power control."""
        print("Test 10: Power Control")
        self.display.fill(0)
        self.display.text("Power Off in 2s", 5, 28)
        self.display.show()
        time.sleep(2)

        self.display.poweroff()
        time.sleep(2)
        self.display.poweron()

        self.display.fill(0)
        self.display.text("Power restored!", 5, 28)
        self.display.show()
        self.clear_and_wait()

    def test_bitmap(self):
        """Test bitmap drawing."""
        print("Test 11: Bitmap Drawing")
        self.display.fill(0)

        # Simple 16x16 heart bitmap
        heart = bytearray([
            0b00000000, 0b00000000,
            0b01100000, 0b00000110,
            0b11110000, 0b00001111,
            0b11111000, 0b00011111,
            0b11111100, 0b00111111,
            0b11111110, 0b01111111,
            0b11111111, 0b11111111,
            0b11111111, 0b11111111,
            0b01111111, 0b11111110,
            0b00111111, 0b11111100,
            0b00011111, 0b11111000,
            0b00001111, 0b11110000,
            0b00000111, 0b11100000,
            0b00000011, 0b11000000,
            0b00000001, 0b10000000,
            0b00000000, 0b00000000,
        ])

        # Draw hearts
        self.display.draw_bitmap(20, 24, heart, 16, 16, 1)
        self.display.draw_bitmap(56, 24, heart, 16, 16, 1)
        self.display.draw_bitmap(92, 24, heart, 16, 16, 1)

        self.display.text("Bitmaps!", 35, 50)
        self.display.show()
        self.clear_and_wait()

    def test_animation(self):
        """Test simple animation."""
        print("Test 12: Animation")

        # Bouncing ball
        x, y = 64, 32
        dx, dy = 3, 2
        radius = 8

        for _ in range(100):
            self.display.fill(0)

            # Draw border
            self.display.rect(0, 0, self.width, self.height, 1)

            # Update position
            x += dx
            y += dy

            # Bounce off walls
            if x <= radius or x >= self.width - radius:
                dx = -dx
            if y <= radius or y >= self.height - radius:
                dy = -dy

            # Draw ball
            self.display.circle(x, y, radius, 1, fill=True)

            self.display.show()
            time.sleep(0.03)

        self.clear_and_wait(1)

    def test_pattern(self):
        """Test pattern display."""
        print("Test 13: Patterns")

        # Checkerboard pattern
        self.display.fill(0)
        for x in range(0, self.width, 8):
            for y in range(0, self.height, 8):
                if (x // 8 + y // 8) % 2:
                    self.display.fill_rect(x, y, 8, 8, 1)
        self.display.show()
        time.sleep(2)

        # Gradient pattern (dithered)
        self.display.fill(0)
        patterns = [
            0b10000000,
            0b10001000,
            0b10100010,
            0b10101010,
            0b10101011,
            0b10111011,
            0b11101111,
            0b11111111,
        ]

        zone_width = self.width // 8
        for zone in range(8):
            for y in range(self.height):
                for x in range(zone * zone_width, (zone + 1) * zone_width):
                    if patterns[zone] & (1 << (x % 8)):
                        self.display.pixel(x, y, 1)

        self.display.show()
        self.clear_and_wait()

    def test_mixed_graphics(self):
        """Test mixed graphics elements."""
        print("Test 14: Mixed Graphics")
        self.display.fill(0)

        # Title bar
        self.display.fill_rect(0, 0, self.width, 12, 1)
        self.display.text("Dashboard", 30, 2, 0)

        # Graph area
        self.display.rect(5, 15, 60, 45, 1)

        # Simulate graph data
        import random
        prev_y = 40
        for x in range(10, 60, 5):
            y = random.randint(20, 55)
            self.display.line(x - 5, prev_y, x, y, 1)
            prev_y = y

        # Status indicators
        self.display.circle(85, 25, 8, 1, fill=True)
        self.display.text("ON", 78, 38)

        self.display.circle(115, 25, 8, 1)
        self.display.text("OFF", 105, 38)

        # Footer
        self.display.hline(0, 52, self.width, 1)
        self.display.text("Status: OK", 30, 55)

        self.display.show()
        self.clear_and_wait(3)

    def run_all_tests(self):
        """Run all display tests."""
        print("\n" + "=" * 40)
        print("SH1106 OLED Display Test Suite")
        print("=" * 40 + "\n")

        tests = [
            ("Basic Text", self.test_basic_text),
            ("Pixels", self.test_pixels),
            ("Lines", self.test_lines),
            ("Rectangles", self.test_rectangles),
            ("Circles", self.test_circles),
            ("Triangles", self.test_triangles),
            ("Contrast", self.test_contrast),
            ("Invert", self.test_invert),
            ("Scroll", self.test_scroll),
            ("Power", self.test_power),
            ("Bitmap", self.test_bitmap),
            ("Animation", self.test_animation),
            ("Patterns", self.test_pattern),
            ("Mixed Graphics", self.test_mixed_graphics),
        ]

        for name, test_func in tests:
            try:
                test_func()
                print(f"  ✓ {name} - PASSED")
            except Exception as e:
                print(f"  ✗ {name} - FAILED: {e}")

        # Final message
        self.display.fill(0)
        self.display.text("All Tests", 25, 20)
        self.display.text("Complete!", 30, 35)
        self.display.show()

        print("\n" + "=" * 40)
        print("Test Suite Complete")
        print("=" * 40 + "\n")


def scan_i2c(i2c):
    """Scan I2C bus and print found devices."""
    print("Scanning I2C bus...")
    devices = i2c.scan()

    if devices:
        print(f"Found {len(devices)} device(s):")
        for device in devices:
            print(f"  - Address: 0x{device:02X}")
    else:
        print("No I2C devices found!")

    return devices


def main():
    """Main test function."""
    print("\nInitializing I2C bus...")
    print("SDA: GP12, SCL: GP13")

    # Initialize I2C bus ONCE
    # This single I2C instance is shared across all tests
    i2c = I2C(
        0,                      # I2C bus 0
        sda=Pin(12),           # GP12 for SDA
        scl=Pin(13),           # GP13 for SCL
        freq=400000            # 400 kHz
    )

    # Scan for devices
    devices = scan_i2c(i2c)

    # Check if display is found
    if 0x3C not in devices:
        print("\nERROR: SH1106 display not found at address 0x3C!")
        print("Please check your wiring:")
        print("  - SDA connected to GP12")
        print("  - SCL connected to GP13")
        print("  - VCC connected to 3.3V")
        print("  - GND connected to GND")
        return

    print("\nSH1106 display found at 0x3C")
    print("Starting tests...\n")

    # Create tester with the shared I2C bus
    tester = DisplayTester(i2c, addr=0x3C)

    # Run all tests
    tester.run_all_tests()


def quick_test():
    """Quick test to verify display is working."""
    print("\nQuick Test Mode")
    print("=" * 30)

    # Initialize I2C bus ONCE
    i2c = I2C(0, sda=Pin(12), scl=Pin(13), freq=400000)

    # Scan and verify
    devices = scan_i2c(i2c)
    if 0x3C not in devices:
        print("Display not found!")
        return

    # Initialize display
    display = SH1106(i2c, addr=0x3C)

    # Simple test
    display.fill(0)
    display.text("Hello World!", 15, 10)
    display.text("Pico 2W", 35, 25)
    display.text("SH1106 OLED", 20, 40)
    display.rect(0, 0, 128, 64, 1)
    display.show()

    print("Display should show 'Hello World!'")
    print("Quick test complete!")


# Run when executed directly
if __name__ == "__main__":
    # Uncomment one of these:
    main()          # Run full test suite
    # quick_test()  # Run quick verification test
