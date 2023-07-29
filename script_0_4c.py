from machine import Pin, PWM
from time import sleep_ms
led_1 = PWM(Pin(2))
led_1.freq(1200)
while True:
    for pc in range(25):
        led_1.duty_u16(pc * 0xffff // 100)
        sleep_ms(200)
    for pc in range(25, 0, -1):
        led_1.duty_u16(pc * 0xffff // 100)
        sleep_ms(200)
