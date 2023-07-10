""" develop button input """
import uasyncio as asyncio
from machine import Pin
from micropython import const
from time import ticks_ms, ticks_diff


class Button:
    """ button with press and hold states """
    
    action_dict = {0: 'none', 1: 'press', 2: 'hold'}
    hold_t = 750  # ms

    def __init__(self, pin):
        self.pin = pin
        self._hw_in = Pin(pin, Pin.IN, Pin.PULL_UP)
        self.action = 0
        self.button_ev = asyncio.Event()
        self.run = True

    async def poll_input(self):
        """ poll button for press and hold events """
        on_time = 0
        prev_state = 0
        while self.run:
            state = 0 if self._hw_in.value() == 1 else 1
            if state != prev_state:
                time_ = ticks_ms()
                if state == 0:
                    if ticks_diff(time_, on_time) < self.hold_t:
                        self.action = 1
                    else:
                        self.action = 2
                    self.button_ev.set()
                else:
                    on_time = time_
                prev_state = state
            await asyncio.sleep_ms(20)

    async def button_event(self):
        """ respond to button event
            - clear event
        """
        while True:
            await self.button_ev.wait()
            self.button_ev.clear()
            self.print_action()
            if self.pin == 22 and self.action == 2:
                self.run = False

    def print_action(self):
        """ print last button action """
        print(
            f'Button: {self.pin}: {self.action_dict[self.action]}')


class ButtonGroup:
    """ group of Button objects """

    def __init__(self, button_pins_):
        self.pins = button_pins_
        self.buttons = {pin: Button(pin) for pin in button_pins_}
        self.n_buttons = len(button_pins_)
        self.states = {pin: 0 for pin in button_pins_}

    def get_states(self):
        """ scan button states """
        for pin in self.pins:
            self.states[pin] = self.buttons[pin].action
            self.buttons[pin].action = 0
        return self.states
    
    def clear_states(self):
        """ set all button states to 0 """
        for pin in self.pins:
            self.states[pin] = 0


async def main():
    """ test button input """
    print('In main()')
    
    btn_group = ButtonGroup([20, 21, 22])
    for pin in btn_group.pins:    
        asyncio.create_task(btn_group.buttons[pin].button_event())
        asyncio.create_task(btn_group.buttons[pin].poll_input())
    while True:
        btn_group.clear_states()
        states = btn_group.get_states()
        print(states)
        await asyncio.sleep_ms(1_000)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
