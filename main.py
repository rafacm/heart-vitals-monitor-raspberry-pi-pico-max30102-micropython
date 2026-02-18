from machine import I2C, Pin

from max30102 import MAX30102, MAX30105_PULSE_AMP_MEDIUM
from sh1106 import SH1106
from heart_vitals_display import HeartVitalsDisplay

i2c1 = I2C(1, sda=Pin(18), scl=Pin(19), freq=400_000)   # MAX30102
i2c0 = I2C(0, sda=Pin(12), scl=Pin(13), freq=400_000)   # SH1106

sensor  = MAX30102(i2c=i2c1)
display = SH1106(i2c=i2c0, addr=0x3C)

sensor.setup_sensor(
    led_mode=2,
    adc_range=16384,
    sample_rate=400,
    led_power=MAX30105_PULSE_AMP_MEDIUM,
    sample_avg=8,
    pulse_width=411,
)

vitals = HeartVitalsDisplay(sensor, display)

while True:
    vitals.update()
