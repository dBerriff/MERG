"""
    GPIO switch input and LED output
"""

from machine import Pin
from time import sleep_ms


class HwSwitch:
    """
        input pin class for hardware switch or button
        - Pull.UP logic
        - returned states: 0 for off (open), 1 for on (closed)
        - this inverts pull-up logic
    """

    def __init__(self, pin):
        self.pin = pin  # for diagnostics
        self._hw_in = Pin(pin, Pin.IN, Pin.PULL_UP)

    def get_state(self):
        """ get switch state off (0) or on (1) """
        return 0 if self._hw_in.value() == 1 else 1


class LedOut:
    """ output pin for LED """

    def __init__(self, pin):
        self.pin = pin  # for diagnostics
        self._pin_out = Pin(pin, Pin.OUT)
        self.state = None
        
    def set_state(self, value):
        """ set output to off (0) or on (1) """
        self._pin_out.value(value)
        self.state = value


def main():
    """ test HwSwitch and LedOut classes """
    print('In main()')

    # test single switch/button to LED operation

    switch = HwSwitch(20)
    led = LedOut(2)

    while True:
        sw_state = switch.get_state()
        print(f'input pin: {switch.pin} switch state: {sw_state}')
        led.set_state(sw_state)
        print(f'LED pin: {led.pin} led state: {led.state}')
        sleep_ms(200)
    

if __name__ == '__main__':
    main()
