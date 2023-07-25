"""
    Use Pulse Width Modulation to set perceived LED output level
"""

from machine import Pin, PWM
from micropython import const
from time import sleep_ms


class LedDriver:
    """ modulate PWM output to change LED brightness
        - duty cycle set as integer percent, 0 - 100
        - inheritance not used
    """

    ZDC = const(0)
    FDC = const(0xffff)
    PC_DC = {pc: round(pc / 100 * FDC) for pc in range(101)}

    def __init__(self, pin, freq):
        self.pin = pin
        self.freq = freq
        # instantiate, then set parameter(s)
        self.pwm = PWM(Pin(pin))
        self.pwm.freq(freq)

    def set_pc(self, pc):
        """ set output duty-cycle """
        if 0 <= pc <= 100:
            self.pwm.duty_u16(self.PC_DC[pc])
        else:
            print(f'duty cycle: {pc} not implemented')


def main():
    """ test of LED PWM """
    led_1 = LedDriver(6, 1200)
    print(f'frequency: {led_1.freq}Hz, zero dc: {led_1.ZDC}, full dc: {led_1.FDC}')

    for i in range(10):
        # pc is percent duty cycle
        for pc in range(26):  # 0, 1, ..., 25
            led_1.set_pc(pc)
            sleep_ms(100)
        sleep_ms(200)
        for pc in range(25, -1, -1):  # 25, 24, ..., 0
            led_1.set_pc(pc)
            sleep_ms(100)
        sleep_ms(200)


if __name__ == '__main__':
    main()
