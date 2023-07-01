"""
    GPIO switch input
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
        """ check for switch state """
        return 0 if self._hw_in.value() == 1 else 1


def main():
    """ test HwSwitch class """
    print('In main()')
    
    # test single switch/button operation
    
    switch = HwSwitch(20)
    while True:
        state = switch.get_state()
        print(f'pin: {switch.pin} switch state: {state}')
        sleep_ms(1000)
    

if __name__ == '__main__':
    main()
