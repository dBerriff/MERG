""" Use Pulse Width Modulation to set perceived LED output level """

from machine import Pin, PWM
from micropython import const


class LedDriver(PWM):
    """ modulate PWM output to change LED brightness
        - duty cycle set as integer percent, 0 - 100
    """

    PC_DC = {pc: round(pc * 0xffff // 100) for pc in range(101)}

    def __init__(self, pin, freq):
        super().__init__(Pin(pin))
        self.freq(freq)
        self.id = pin

    def set_pc(self, pc):
        """ set output duty-cycle """
        if 0 <= pc <= 100:
            self.duty_u16(self.PC_DC[pc])
        else:
            print(f'duty cycle: {pc} not implemented')


def main():
    """ test of LED PWM """
    from time import sleep_ms
    led_1 = LedDriver(2, 1200)
    print(f'id: {led_1.id}; frequency: {led_1.freq()}Hz')

    led_1.set_pc(0)
    sleep_ms(1000)
    for _ in range(1):
        # pc is percent duty cycle
        for pc in range(26):  # 0, 1, ..., 25
            led_1.set_pc(pc)
            sleep_ms(200)
        for pc in range(25, -1, -1):  # 25, 24, ..., 0
            led_1.set_pc(pc)
            sleep_ms(200)
        sleep_ms(1000)


if __name__ == '__main__':
    main()
