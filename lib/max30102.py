from machine import I2C, SoftI2C
from array import array
from utime import sleep_ms

# Register addresses
_REG_INT_STAT_1     = 0x00
_REG_INT_STAT_2     = 0x01
_REG_FIFO_WR_PTR    = 0x04
_REG_FIFO_OVF       = 0x05
_REG_FIFO_RD_PTR    = 0x06
_REG_FIFO_DATA      = 0x07
_REG_FIFO_CFG       = 0x08
_REG_MODE_CFG       = 0x09
_REG_SPO2_CFG       = 0x0A
_REG_LED1_AMP       = 0x0C  # RED
_REG_LED2_AMP       = 0x0D  # IR
_REG_LED3_AMP       = 0x0E  # GREEN
_REG_PROX_AMP       = 0x10
_REG_MULTI_LED_1    = 0x11
_REG_MULTI_LED_2    = 0x12
_REG_TEMP_INT       = 0x1F
_REG_TEMP_FRAC      = 0x20
_REG_TEMP_CFG       = 0x21
_REG_PART_ID        = 0xFF

# LED amplitude presets
LED_AMP_LOWEST = 0x02   # 0.4 mA  — ~4 inch range
LED_AMP_LOW    = 0x1F   # 6.4 mA  — ~8 inch range
LED_AMP_MEDIUM = 0x7F   # 25.4 mA — ~8 inch range
LED_AMP_HIGH   = 0xFF   # 50.0 mA — ~12 inch range

# Lookup tables replacing if/elif chains
_SAMPLE_AVG = {1: 0x00, 2: 0x20, 4: 0x40, 8: 0x60, 16: 0x80, 32: 0xA0}

_SAMPLE_RATE = {
    50: 0x00, 100: 0x04, 200: 0x08, 400: 0x0C,
    800: 0x10, 1000: 0x14, 1600: 0x18, 3200: 0x1C,
}

_PULSE_WIDTH = {69: 0x00, 118: 0x01, 215: 0x02, 411: 0x03}

_ADC_RANGE = {2048: 0x00, 4096: 0x20, 8192: 0x40, 16384: 0x60}

_LED_MODE = {1: 0x02, 2: 0x03, 3: 0x07}

# Internal constants
_RESET_BIT    = 0x40
_SHUTDOWN_BIT = 0x80
_ROLLOVER_BIT = 0x10
_EXPECTED_ID  = 0x15
_BUF_SIZE     = 16

# Slot device codes
_SLOT_RED = 0x01
_SLOT_IR  = 0x02


class MAX30102:
    def __init__(self, i2c, addr=0x57):
        self._i2c = i2c
        self._addr = addr
        self._active_leds = 0
        self._bytes_per_sample = 0

        # Pre-allocated ring buffers (red, IR)
        self._red = array('l', [0] * _BUF_SIZE)
        self._ir  = array('l', [0] * _BUF_SIZE)
        self._head = 0
        self._tail = 0

    # ---- public API --------------------------------------------------------

    def setup_sensor(self, led_mode=2, adc_range=16384, sample_rate=400,
                     led_power=LED_AMP_MEDIUM, sample_avg=8, pulse_width=411):
        self.soft_reset()
        self._set_sample_avg(sample_avg)
        self._enable_fifo_rollover()
        self._set_led_mode(led_mode)
        self._set_adc_range(adc_range)
        self._set_sample_rate(sample_rate)
        self._set_pulse_width(pulse_width)
        self._set_led_amplitudes(led_power)
        self._clear_fifo()

    def shutdown(self):
        self._bitmask(_REG_MODE_CFG, 0x7F, _SHUTDOWN_BIT)

    def soft_reset(self):
        self._bitmask(_REG_MODE_CFG, 0xBF, _RESET_BIT)
        while True:
            sleep_ms(10)
            v = self._read_reg(_REG_MODE_CFG)
            if not (v & _RESET_BIT):
                break

    def check(self):
        rd = self._read_reg(_REG_FIFO_RD_PTR)
        wr = self._read_reg(_REG_FIFO_WR_PTR)
        if rd == wr:
            return False

        n = (wr - rd) & 0x1F  # 32-slot circular pointer
        for _ in range(n):
            raw = self._read_fifo_sample()
            # Decode RED (bytes 0-2)
            red_val = (raw[0] << 16 | raw[1] << 8 | raw[2]) & 0x3FFFF
            h = self._head
            self._red[h] = red_val
            if self._active_leds > 1:
                ir_val = (raw[3] << 16 | raw[4] << 8 | raw[5]) & 0x3FFFF
                self._ir[h] = ir_val
            self._head = (h + 1) % _BUF_SIZE
            # If head catches tail, advance tail (drop oldest)
            if self._head == self._tail:
                self._tail = (self._tail + 1) % _BUF_SIZE
        return True

    def available(self):
        return (self._head - self._tail) % _BUF_SIZE

    def pop_ir_from_storage(self):
        if self._head == self._tail:
            return 0
        val = self._ir[self._tail]
        self._tail = (self._tail + 1) % _BUF_SIZE
        return val

    def pop_red_from_storage(self):
        if self._head == self._tail:
            return 0
        val = self._red[self._tail]
        self._tail = (self._tail + 1) % _BUF_SIZE
        return val

    def check_part_id(self):
        return self._read_reg(_REG_PART_ID) == _EXPECTED_ID

    def read_temperature(self):
        self._write_reg(_REG_TEMP_CFG, 0x01)
        sleep_ms(100)
        while self._read_reg(_REG_INT_STAT_2) & 0x02:
            sleep_ms(1)
        t_int  = self._read_reg(_REG_TEMP_INT)
        t_frac = self._read_reg(_REG_TEMP_FRAC)
        return float(t_int) + float(t_frac) * 0.0625

    def check_finger(self, threshold=10000):
        self.check()
        ir = self.pop_ir_from_storage()
        return ir > threshold

    # ---- private configuration methods -------------------------------------

    def _set_sample_avg(self, avg):
        val = _SAMPLE_AVG.get(avg)
        if val is None:
            raise ValueError('Invalid sample_avg: {}'.format(avg))
        self._bitmask(_REG_FIFO_CFG, 0x1F, val)

    def _enable_fifo_rollover(self):
        self._bitmask(_REG_FIFO_CFG, 0xEF, _ROLLOVER_BIT)

    def _set_led_mode(self, mode):
        val = _LED_MODE.get(mode)
        if val is None:
            raise ValueError('Invalid led_mode: {}'.format(mode))
        self._bitmask(_REG_MODE_CFG, 0xF8, val)
        self._active_leds = mode
        self._bytes_per_sample = mode * 3

        # Configure multi-LED slot registers
        self._bitmask(_REG_MULTI_LED_1, 0xF8, _SLOT_RED)
        if mode > 1:
            self._bitmask(_REG_MULTI_LED_1, 0x8F, _SLOT_IR << 4)

    def _set_adc_range(self, adc_range):
        val = _ADC_RANGE.get(adc_range)
        if val is None:
            raise ValueError('Invalid adc_range: {}'.format(adc_range))
        self._bitmask(_REG_SPO2_CFG, 0x9F, val)

    def _set_sample_rate(self, rate):
        val = _SAMPLE_RATE.get(rate)
        if val is None:
            raise ValueError('Invalid sample_rate: {}'.format(rate))
        self._bitmask(_REG_SPO2_CFG, 0xE3, val)

    def _set_pulse_width(self, width):
        val = _PULSE_WIDTH.get(width)
        if val is None:
            raise ValueError('Invalid pulse_width: {}'.format(width))
        self._bitmask(_REG_SPO2_CFG, 0xFC, val)

    def _set_led_amplitudes(self, power):
        self._write_reg(_REG_LED1_AMP, power)
        self._write_reg(_REG_LED2_AMP, power)
        self._write_reg(_REG_LED3_AMP, power)
        self._write_reg(_REG_PROX_AMP, power)

    def _clear_fifo(self):
        self._write_reg(_REG_FIFO_WR_PTR, 0)
        self._write_reg(_REG_FIFO_OVF, 0)
        self._write_reg(_REG_FIFO_RD_PTR, 0)
        self._head = 0
        self._tail = 0

    # ---- low-level I2C helpers ---------------------------------------------

    def _read_reg(self, reg, n=1):
        self._i2c.writeto(self._addr, bytearray([reg]))
        data = self._i2c.readfrom(self._addr, n)
        return data[0] if n == 1 else data

    def _write_reg(self, reg, val):
        self._i2c.writeto(self._addr, bytearray([reg, val]))

    def _bitmask(self, reg, mask, bits):
        cur = self._read_reg(reg)
        self._write_reg(reg, (cur & mask) | bits)

    def _read_fifo_sample(self):
        return self._read_reg(_REG_FIFO_DATA, self._bytes_per_sample)
