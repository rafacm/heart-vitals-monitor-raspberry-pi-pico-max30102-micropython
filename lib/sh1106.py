"""
SH1106 OLED Display Driver for MicroPython
Supports 128x64 OLED displays via I2C

Author: Assistant
Compatible with: Raspberry Pi Pico and other MicroPython boards
"""

import framebuf
import time


class SH1106:
    """
    SH1106 OLED Display Driver

    This driver inherits from framebuf.FrameBuffer to provide
    drawing primitives like text, lines, rectangles, etc.
    """

    # SH1106 Commands
    CMD_SET_CONTRAST = 0x81
    CMD_DISPLAY_ALL_ON_RESUME = 0xA4
    CMD_DISPLAY_ALL_ON = 0xA5
    CMD_NORMAL_DISPLAY = 0xA6
    CMD_INVERT_DISPLAY = 0xA7
    CMD_DISPLAY_OFF = 0xAE
    CMD_DISPLAY_ON = 0xAF
    CMD_SET_DISPLAY_OFFSET = 0xD3
    CMD_SET_COM_PINS = 0xDA
    CMD_SET_VCOM_DETECT = 0xDB
    CMD_SET_DISPLAY_CLOCK_DIV = 0xD5
    CMD_SET_PRECHARGE = 0xD9
    CMD_SET_MULTIPLEX = 0xA8
    CMD_SET_LOW_COLUMN = 0x00
    CMD_SET_HIGH_COLUMN = 0x10
    CMD_SET_START_LINE = 0x40
    CMD_MEMORY_MODE = 0x20
    CMD_COLUMN_ADDR = 0x21
    CMD_PAGE_ADDR = 0x22
    CMD_COM_SCAN_INC = 0xC0
    CMD_COM_SCAN_DEC = 0xC8
    CMD_SEG_REMAP = 0xA0
    CMD_CHARGE_PUMP = 0x8D
    CMD_SET_PAGE_ADDR = 0xB0

    def __init__(self, i2c, width=128, height=64, addr=0x3C, rotate=0):
        """
        Initialize the SH1106 display.

        Args:
            i2c: Initialized I2C bus object
            width: Display width in pixels (default: 128)
            height: Display height in pixels (default: 64)
            addr: I2C address of the display (default: 0x3C)
            rotate: Rotation (0 or 180 degrees)
        """
        self.i2c = i2c
        self.addr = addr
        self.width = width
        self.height = height
        self.rotate = rotate
        self.pages = height // 8
        self.external_vcc = False

        # SH1106 has 132 columns, but display is 128 pixels
        # Offset of 2 pixels on each side
        self.column_offset = 2

        # Create frame buffer
        # Buffer size: width * pages (each page is 8 pixels high)
        self.buffer = bytearray(self.width * self.pages)
        self.framebuf = framebuf.FrameBuffer(
            self.buffer, self.width, self.height, framebuf.MONO_VLSB
        )

        # Initialize display
        self._init_display()

    def _init_display(self):
        """Initialize the display with proper settings."""
        init_sequence = [
            self.CMD_DISPLAY_OFF,
            self.CMD_SET_DISPLAY_CLOCK_DIV, 0x80,
            self.CMD_SET_MULTIPLEX, self.height - 1,
            self.CMD_SET_DISPLAY_OFFSET, 0x00,
            self.CMD_SET_START_LINE | 0x00,
            self.CMD_CHARGE_PUMP, 0x10 if self.external_vcc else 0x14,
            self.CMD_MEMORY_MODE, 0x00,
            # Segment remap and COM scan direction for rotation
            self.CMD_SEG_REMAP | (0x01 if self.rotate == 0 else 0x00),
            self.CMD_COM_SCAN_DEC if self.rotate == 0 else self.CMD_COM_SCAN_INC,
            self.CMD_SET_COM_PINS, 0x12 if self.height == 64 else 0x02,
            self.CMD_SET_CONTRAST, 0xCF if not self.external_vcc else 0x9F,
            self.CMD_SET_PRECHARGE, 0x22 if self.external_vcc else 0xF1,
            self.CMD_SET_VCOM_DETECT, 0x40,
            self.CMD_DISPLAY_ALL_ON_RESUME,
            self.CMD_NORMAL_DISPLAY,
            self.CMD_DISPLAY_ON,
        ]

        for cmd in init_sequence:
            self._write_cmd(cmd)

        self.fill(0)
        self.show()

    def _write_cmd(self, cmd):
        """Write a command to the display."""
        self.i2c.writeto(self.addr, bytes([0x00, cmd]))

    def _write_data(self, data):
        """Write data to the display."""
        self.i2c.writeto(self.addr, bytes([0x40]) + data)

    def show(self):
        """
        Update the display with the contents of the frame buffer.

        SH1106 doesn't support horizontal addressing mode across pages,
        so we need to update page by page.
        """
        for page in range(self.pages):
            # Set page address
            self._write_cmd(self.CMD_SET_PAGE_ADDR | page)
            # Set column address (with offset for SH1106)
            self._write_cmd(self.CMD_SET_LOW_COLUMN | (self.column_offset & 0x0F))
            self._write_cmd(self.CMD_SET_HIGH_COLUMN | (self.column_offset >> 4))

            # Write page data
            start = page * self.width
            end = start + self.width
            self._write_data(self.buffer[start:end])

    def fill(self, color):
        """
        Fill the entire display with a color.

        Args:
            color: 0 for black, 1 for white
        """
        self.framebuf.fill(color)

    def pixel(self, x, y, color=None):
        """
        Get or set a pixel.

        Args:
            x: X coordinate
            y: Y coordinate
            color: If None, returns pixel value. Otherwise sets pixel.

        Returns:
            Pixel value if color is None
        """
        if color is None:
            return self.framebuf.pixel(x, y)
        self.framebuf.pixel(x, y, color)

    def text(self, string, x, y, color=1):
        """
        Draw text on the display.

        Args:
            string: Text to display
            x: X coordinate
            y: Y coordinate
            color: 0 for black, 1 for white
        """
        self.framebuf.text(string, x, y, color)

    def line(self, x0, y0, x1, y1, color=1):
        """
        Draw a line.

        Args:
            x0, y0: Start coordinates
            x1, y1: End coordinates
            color: 0 for black, 1 for white
        """
        self.framebuf.line(x0, y0, x1, y1, color)

    def hline(self, x, y, width, color=1):
        """
        Draw a horizontal line.

        Args:
            x, y: Start coordinates
            width: Line width
            color: 0 for black, 1 for white
        """
        self.framebuf.hline(x, y, width, color)

    def vline(self, x, y, height, color=1):
        """
        Draw a vertical line.

        Args:
            x, y: Start coordinates
            height: Line height
            color: 0 for black, 1 for white
        """
        self.framebuf.vline(x, y, height, color)

    def rect(self, x, y, width, height, color=1, fill=False):
        """
        Draw a rectangle.

        Args:
            x, y: Top-left coordinates
            width: Rectangle width
            height: Rectangle height
            color: 0 for black, 1 for white
            fill: If True, fill the rectangle
        """
        if fill:
            self.framebuf.fill_rect(x, y, width, height, color)
        else:
            self.framebuf.rect(x, y, width, height, color)

    def fill_rect(self, x, y, width, height, color=1):
        """
        Draw a filled rectangle.

        Args:
            x, y: Top-left coordinates
            width: Rectangle width
            height: Rectangle height
            color: 0 for black, 1 for white
        """
        self.framebuf.fill_rect(x, y, width, height, color)

    def scroll(self, dx, dy):
        """
        Scroll the display contents.

        Args:
            dx: Horizontal scroll amount
            dy: Vertical scroll amount
        """
        self.framebuf.scroll(dx, dy)

    def blit(self, fbuf, x, y, key=-1, palette=None):
        """
        Copy a framebuffer to the display.

        Args:
            fbuf: Source framebuffer
            x, y: Destination coordinates
            key: Transparent color key (-1 for none)
            palette: Color palette
        """
        self.framebuf.blit(fbuf, x, y, key, palette)

    def contrast(self, value):
        """
        Set display contrast.

        Args:
            value: Contrast value (0-255)
        """
        self._write_cmd(self.CMD_SET_CONTRAST)
        self._write_cmd(value)

    def invert(self, invert):
        """
        Invert the display colors.

        Args:
            invert: True to invert, False for normal
        """
        self._write_cmd(self.CMD_INVERT_DISPLAY if invert else self.CMD_NORMAL_DISPLAY)

    def poweroff(self):
        """Turn off the display."""
        self._write_cmd(self.CMD_DISPLAY_OFF)

    def poweron(self):
        """Turn on the display."""
        self._write_cmd(self.CMD_DISPLAY_ON)

    def sleep(self, enable):
        """
        Put display in sleep mode.

        Args:
            enable: True to sleep, False to wake
        """
        self._write_cmd(self.CMD_DISPLAY_OFF if enable else self.CMD_DISPLAY_ON)

    def rotate(self, rotate):
        """
        Rotate the display.

        Args:
            rotate: 0 or 180 degrees
        """
        self._write_cmd(self.CMD_SEG_REMAP | (0x01 if rotate == 0 else 0x00))
        self._write_cmd(self.CMD_COM_SCAN_DEC if rotate == 0 else self.CMD_COM_SCAN_INC)

    def circle(self, x0, y0, radius, color=1, fill=False):
        """
        Draw a circle using Bresenham's algorithm.

        Args:
            x0, y0: Center coordinates
            radius: Circle radius
            color: 0 for black, 1 for white
            fill: If True, fill the circle
        """
        if fill:
            self._fill_circle(x0, y0, radius, color)
        else:
            self._draw_circle(x0, y0, radius, color)

    def _draw_circle(self, x0, y0, radius, color):
        """Draw circle outline using Bresenham's algorithm."""
        x = radius
        y = 0
        err = 0

        while x >= y:
            self.pixel(x0 + x, y0 + y, color)
            self.pixel(x0 + y, y0 + x, color)
            self.pixel(x0 - y, y0 + x, color)
            self.pixel(x0 - x, y0 + y, color)
            self.pixel(x0 - x, y0 - y, color)
            self.pixel(x0 - y, y0 - x, color)
            self.pixel(x0 + y, y0 - x, color)
            self.pixel(x0 + x, y0 - y, color)

            y += 1
            err += 1 + 2 * y
            if 2 * (err - x) + 1 > 0:
                x -= 1
                err += 1 - 2 * x

    def _fill_circle(self, x0, y0, radius, color):
        """Draw filled circle."""
        x = radius
        y = 0
        err = 0

        while x >= y:
            self.hline(x0 - x, y0 + y, 2 * x + 1, color)
            self.hline(x0 - y, y0 + x, 2 * y + 1, color)
            self.hline(x0 - x, y0 - y, 2 * x + 1, color)
            self.hline(x0 - y, y0 - x, 2 * y + 1, color)

            y += 1
            err += 1 + 2 * y
            if 2 * (err - x) + 1 > 0:
                x -= 1
                err += 1 - 2 * x

    def triangle(self, x0, y0, x1, y1, x2, y2, color=1, fill=False):
        """
        Draw a triangle.

        Args:
            x0, y0, x1, y1, x2, y2: Triangle vertices
            color: 0 for black, 1 for white
            fill: If True, fill the triangle
        """
        if fill:
            self._fill_triangle(x0, y0, x1, y1, x2, y2, color)
        else:
            self.line(x0, y0, x1, y1, color)
            self.line(x1, y1, x2, y2, color)
            self.line(x2, y2, x0, y0, color)

    def _fill_triangle(self, x0, y0, x1, y1, x2, y2, color):
        """Draw filled triangle using scanline algorithm."""
        # Sort vertices by y coordinate
        if y0 > y1:
            x0, y0, x1, y1 = x1, y1, x0, y0
        if y1 > y2:
            x1, y1, x2, y2 = x2, y2, x1, y1
        if y0 > y1:
            x0, y0, x1, y1 = x1, y1, x0, y0

        if y0 == y2:  # Degenerate case
            return

        for y in range(y0, y2 + 1):
            if y < y1:
                xa = x0 + (x1 - x0) * (y - y0) // (y1 - y0) if y1 != y0 else x0
                xb = x0 + (x2 - x0) * (y - y0) // (y2 - y0)
            else:
                xa = x1 + (x2 - x1) * (y - y1) // (y2 - y1) if y2 != y1 else x1
                xb = x0 + (x2 - x0) * (y - y0) // (y2 - y0)

            if xa > xb:
                xa, xb = xb, xa
            self.hline(xa, y, xb - xa + 1, color)

    def draw_bitmap(self, x, y, bitmap, width, height, color=1):
        """
        Draw a bitmap image.

        Args:
            x, y: Top-left coordinates
            bitmap: Bytearray of bitmap data (MSB first)
            width: Bitmap width
            height: Bitmap height
            color: 0 for black, 1 for white
        """
        byte_width = (width + 7) // 8
        for j in range(height):
            for i in range(width):
                byte_idx = j * byte_width + i // 8
                bit_idx = 7 - (i % 8)
                if bitmap[byte_idx] & (1 << bit_idx):
                    self.pixel(x + i, y + j, color)

    def clear(self):
        """Clear the display (fill with black)."""
        self.fill(0)
        self.show()


class SH1106_SPI:
    """
    SH1106 OLED Display Driver for SPI interface.

    Note: This class is provided for completeness but the I2C
    version is recommended for the given hardware setup.
    """

    def __init__(self, spi, dc, res, cs, width=128, height=64):
        """
        Initialize the SH1106 display via SPI.

        Args:
            spi: Initialized SPI bus object
            dc: Data/Command pin
            res: Reset pin
            cs: Chip select pin
            width: Display width in pixels
            height: Display height in pixels
        """
        raise NotImplementedError("SPI interface not implemented. Use I2C version.")
