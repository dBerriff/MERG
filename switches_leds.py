"""
    classes for GPIO switched input and output
    pin states returned or set as:
    - 0 is Off, 1 is On
    - maps onto bool False and True in Python
    - input: inverts input pull-up logic
"""

from machine import Pin
from micropython import const
from time import sleep_ms


def get_keys(dictionary_: dict) -> tuple:
    """ return a sorted tuple of dictionary_ keys """
    keys = list(dictionary_.keys())
    keys.sort()
    return tuple(keys)


class HwSwitch:
    """
        input pin class for hardware switch (or button)
        - Pull.UP logic
    """

    # debounce values
    # 3 checks require 2 pauses
    n_checks = const(3)
    i_max = const(n_checks - 1)  # index for final check
    check_pause = const(20 // i_max)  # ms - around 20ms for checks

    def __init__(self, pin):
        self.pin = pin  # for diagnostics
        self.hw_in = Pin(pin, Pin.IN, Pin.PULL_UP)
        # pull-up pins are 1 if open
        self._inputs = [1] * self.n_checks

    def get_state(self) -> int:
        """ check for switch state """
        return 0 if self.hw_in.value() else 1  # 0 for On

    def get_state_db(self) -> int:
        """ de-bounced check for switch state """
        get_value = self.hw_in.value  # alias for input value method
        for i in range(self.i_max):
            self._inputs[i] = get_value()
            sleep_ms(self.check_pause)
        self._inputs[self.i_max] = get_value()  # no pause after final input
        return 0 if any(self._inputs) else 1  # all must be 0 for On

    def __str__(self):
        return f'HwSwitch on pin({self.pin})'


class PinOut:
    """ output pin; set off or on """

    def __init__(self, pin):
        self.pin = pin  # for diagnostics
        self.pin_out = Pin(pin, Pin.OUT)

    def set_state(self, value):
        """ set output to Off or On """
        if value == 1:
            self.pin_out.on()
        else:
            self.pin_out.off()

    def __str__(self):
        return f'PinOut on pin({self.pin})'


class HwSwitchGroup:
    """ instantiate a group of HwSwitch objects """

    def __init__(self, switch_pins_):
        self.switches = {pin: HwSwitch(pin) for pin in switch_pins_}
        self.n_switches = len(switch_pins_)
        self.pins = switch_pins_
        self._states = {pin: 0 for pin in switch_pins_}

    def get_states(self):
        """ poll switch states """
        for pin in self.pins:
            self._states[pin] = self.switches[pin].get_state()
        return self._states

    def print_states(self):
        """ print states in pin order """
        states = ''
        for pin in self.pins:
            states += f'{pin}: {self._states[pin]}, '
        print(states[:-2])


def main():
    """ test polling of switch inputs """
    print('In main()')

    # === test data

    switch_pins = (20, 21, 22)
    led_pins = (0, 1, 2)
    switch_led = {20: 0, 21: 1, 22: 2}  # switch_pin: led_pin

    # ===

    switch_group = HwSwitchGroup(switch_pins)
    leds = {pin: PinOut(pin) for pin in led_pins}

    poll_interval = 200  # ms
    print('Poll switches')
    prev_states = {}
    while True:
        states = switch_group.get_states()
        if states != prev_states:
            print(states)
            for pin in states:
                led_pin = switch_led[pin]
                leds[led_pin].set_state(states[pin])
                prev_states[pin] = states[pin]  # keep dicts distinct!
        sleep_ms(poll_interval)


if __name__ == '__main__':
    main()
