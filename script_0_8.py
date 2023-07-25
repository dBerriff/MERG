"""
    set servos from hardware switch input
    N.B. Demonstration code: prioritises clarity before efficiency
    - servos are set asynchronously
"""

import uasyncio as asyncio
from script_0_3 import HwSwitchGroup
from script_0_7 import ServoGroup


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
    
    servo_pins = (0, 1, 2, 3)
    # {pin: (off_deg, on_deg, transition_time)}
    servo_params = {[70, 110],
                    [110, 70],
                    [45, 135],
                    [45, 135]
                    }

    servo_init = {0, 0, 0, 0}
    
    # {switch-pin: (servo-pin, ...), ...}
    switch_servos = {16: [0, 1],
                     17: [2],
                     18: [3]
                     }

    # === end of parameters
    
    switch_group = HwSwitchGroup(switch_pins)
    servo_group = ServoGroup(servo_pins, servo_params)
    print('initialising servos...')
    servo_group.initialise(servo_init)
    print('servos initialised')
    while True:
        sw_states = switch_group.get_states()
        result = await servo_group.match_demand(
            get_servo_demand(sw_states, switch_servos))
        if 0 in result or 1 in result:
            print(result)
        await asyncio.sleep_ms(1000)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
