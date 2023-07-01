"""
    set servos from switch input
    - servos are set asynchronously
"""

import uasyncio as asyncio
from machine import Pin, PWM
from time import sleep_ms
from script_0_3 import HwSwitchGroup
from script_0_7 import ServoSG90, ServoGroup


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
    
    switch_pins = list(switch_servos.keys())
    switch_pins.sort()
    switch_pins = tuple(switch_pins)

    switch_group = HwSwitchGroup(switch_pins)
    servo_group = ServoGroup(servo_params, switch_servos)
    print('initialising servos...')
    servo_group.initialise(servo_init)
    print('servo_group initialised')
    prev_states = {}
    servo_demand = {}
    while True:
        sw_states = switch_group.get_states()
        if sw_states != prev_states:
            print(f'switch demand: {sw_states}')
            result = await servo_group.match_demand(
                get_servo_demand(sw_states, switch_servos))
            print(f'servo setting: {result}')
            print()
            for key in sw_states:
                prev_states[key] = sw_states[key]
        await asyncio.sleep_ms(500)

    
if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
