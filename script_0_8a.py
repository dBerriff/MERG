"""
    set servos from hardware switch input
    - hardware switch de-bounce
    - servos are set asynchronously
"""

import uasyncio as asyncio
from machine import Pin
from micropython import const
from script_0_7 import ServoGroup


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


class HwSwitchGroup:
    """ instantiate a group of HwSwitch objects """

    def __init__(self, switch_pins_):
        self.switches = {pin: HwSwitch(pin) for pin in switch_pins_}
        self.n_switches = len(switch_pins_)
        self.pins = switch_pins_
        self._states = {pin: 0 for pin in self.pins}
        self.tasks = [None] * self.n_switches  # for tasks in get_states_db

    def get_states(self):
        """ poll switch states """
        self._states = {
            pin: self.switches[pin].get_state() for pin in self.pins}
        return self._states

    async def get_states_db(self):
        """ coro: poll switch states with de-bounce """
        for i, pin in enumerate(self.pins):
            switch = self.switches[pin]
            self.tasks[i] = switch.get_state_db()
        result = await asyncio.gather(*self.tasks)
        for i, pin in enumerate(self.pins):
            self._states[pin] = result[i]
        return self._states

    def print_states(self):
        """ print states in pin order """
        states = ''
        for pin in self.pins:
            states += f'{pin}: {self._states[pin]}, '
        print(states[:-2])


async def main():
    """ module run-time code """
    print('In main()')

    def get_servo_demand(sw_states_, switch_servos_):
        """ return dict of servo setting demands """
        servo_demand = {}
        for sw_pin_ in sw_states_:
            demand_ = sw_states_[sw_pin_]
            for servo_pin_ in switch_servos_[sw_pin_]:
                servo_demand[servo_pin_] = demand_
        return servo_demand

    # === switch and servo parameters

    switch_pins = (16, 17, 18)
    
    # {pin: (off_deg, on_deg, transition_time)}
    servo_params = {0: (70, 110),
                    1: (110, 70),
                    2: (45, 135),
                    3: (45, 135)
                    }

    servo_init = {0: 0, 1: 0, 2: 0, 3: 0}
    
    # {switch-pin: (servo-pin, ...), ...}
    switch_servos = {16: [0, 1],
                     17: [2],
                     18: [3]
                     }

    # === end of parameters
    
    switch_group = HwSwitchGroup(switch_pins)
    servo_group = ServoGroup(servo_params)
    print('initialising servos...')
    servo_group.initialise(servo_init)
    print('servos initialised')
    while True:
        sw_states = await switch_group.get_states_db()
        print(sw_states)
        result = await servo_group.match_demand(
            get_servo_demand(sw_states, switch_servos))
        print(result)
        await asyncio.sleep_ms(1000)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
