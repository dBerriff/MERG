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


class HwSwitchGroup:
    """ instantiate a group of HwSwitch objects """

    def __init__(self, switch_pins_):
        self.switches = {pin: HwSwitch(pin) for pin in switch_pins_}
        self.n_switches = len(switch_pins_)
        self.pins = switch_pins_
        self._states = {pin: 0 for pin in self.pins}

    def get_states(self):
        """ poll switch states """
        self._states = {
            pin: self.switches[pin].get_state() for pin in self.pins}
        return self._states

    def print_states(self):
        """ print states in pin order """
        states = ''
        for pin in self.pins:
            states += f'{pin}: {self._states[pin]}, '
        print(states[:-2])


def main():
    """ test HwSwitchGroup class """
    print('In main()')

    # test multiple switches/buttons to LEDs operation

    # === test data

    switch_pins = (16, 17, 18)
    led_pins = (2, 3, 4, 5)
    # led pins as lists to support multiple LEDs
    switch_led = {16: [2, 3], 17: [4], 18: [5]}  # switch_pin: [led_pin(s)]

    # ===

    switch_group = HwSwitchGroup(switch_pins)
    leds = {pin: LedOut(pin) for pin in led_pins}

    poll_interval = 1_000  # ms
    print('Poll switches')
    while True:
        states = switch_group.get_states()
        print(states)
        for sw_pin in states:
            for led_pin in switch_led[sw_pin]:  # set each connected LED
                leds[led_pin].set_state(states[sw_pin])
        sleep_ms(poll_interval)    


if __name__ == '__main__':
    main()
