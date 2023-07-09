""" develop button input """
import uasyncio as asyncio
from machine import Pin
from micropython import const
from time import ticks_ms, ticks_diff


class HwSwitch:
    """
        input pin class for hardware switch or button
        - Pull.UP logic value(): 1 for switch open, 0 for switch closed
        - get_state() method returns: 0 for off (open), 1 for on (closed)
          inverts pull-up logic
    """

    n_readings = const(3)
    n_pauses = const(n_readings - 1)
    db_pause = const(20 // n_pauses)  # de-bounce over approx 20ms

    def __init__(self, pin):
        self.pin = pin  # for diagnostics
        self._hw_in = Pin(pin, Pin.IN, Pin.PULL_UP)
        self.readings = [1] * self.n_readings

    def get_state(self):
        """ get switch state; returns 0 (off) or 1 (on) """
        return 0 if self._hw_in.value() == 1 else 1

    async def get_state_db(self):
        """ coro: get switch state with simple de-bounce
            - returns 0 (off) or 1 (on)
            - take n_readings over 20ms
        """
        value = self._hw_in.value
        readings = self.readings
        for i in range(self.n_pauses):
            readings[i] = value()
            await asyncio.sleep_ms(self.db_pause)
        readings[self.n_pauses] = value()
        return 0 if any(readings) else 1


class Button:
    """ button with press and hold states """
    
    action_dict = {0: 'none', 1: 'press', 2: 'hold'}

    def __init__(self, pin):
        self.pin = pin
        self.sw = HwSwitch(pin)
        self.action = 0
        self.button_ev = asyncio.Event()

    async def poll_button(self):
        """ poll button for press and hold events """
        hold_threshold = 500  # ms
        on_time = None
        prev_state = 0
        while True:
            current_state = self.sw.get_state()
            current_time = ticks_ms()
            if current_state != prev_state:
                if current_state == 0:
                    hold_time = ticks_diff(current_time, on_time)
                    if hold_time < hold_threshold:
                        self.action = 1
                    else:
                        self.action = 2
                    self.button_ev.set()
                elif current_state == 1:
                    on_time = current_time
                prev_state = current_state
            await asyncio.sleep_ms(20)

    async def button_event(self):
        """ respond to button event
            - clear event
        """
        while True:
            await self.button_ev.wait()
            self.button_ev.clear()
            self.print_action()

    
    def print_action(self):
        """ print last button action """
        print(
            f'Button: {self.pin}: {self.action_dict[self.action]}')
            

async def main():
    """ test button input """
    print('In main()')
    
    button_20 = Button(20)
    asyncio.create_task(button_20.button_event())
    await button_20.poll_button()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
