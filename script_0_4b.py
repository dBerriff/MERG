""" Pulse Width Modulation example; terse """

from machine import Pin, PWM
from micropython import const


class LedDriver(PWM):
    """ set PWM output """

    def __init__(self, pin, freq):
        super().__init__(Pin(pin))
        self.freq(freq)

    def set_pc(self, pc_):
        """ set output duty-cycle """
        self.duty_u16(pc_ * 0xffff // 100)


def main():
    """ test of LED PWM """
    from time import sleep_ms
    led_1 = LedDriver(pin=2, freq=1200)
    up = list(range(25))
    down = list(reversed(up))
    while True:
        for pc in up:
            led_1.set_pc(pc)
            sleep_ms(200)
        for pc in down:
            led_1.set_pc(pc)
            sleep_ms(200)


if __name__ == '__main__':
    main()
