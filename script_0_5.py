"""
    set servos from switch input
    N.B. Demonstration code: prioritises clarity before efficiency
    - servos are set sequentially
"""

from time import sleep_ms
from script_0_3 import HwSwitchGroup
from script_0_4 import ServoGroup


def main():
    """ test mechanical switch setting and response """

    print('In main()')

    # === switch and servo parameters
    
    # {pin: (off_deg, on_deg [, transition_time])}
    # transition time defaults to 3s to match Tortoise turnout motor
    servo_params = {0: [45, 135],
                    1: [135, 45],
                    2: [45, 135],
                    3: [135, 45]
                    }

    servo_init = {0: 0, 1: 0, 2: 0, 3: 0}
    
    # {switch-pin: [servo-pin(s)]}
    switch_servos = {16: [0, 1],
                     17: [2],
                     18: [3]
                     }

    polling_interval = 1_000  # ms

    # === end of parameters
    
    switch_pins = list(switch_servos.keys())
    switch_pins.sort()
    switch_group = HwSwitchGroup(switch_pins)
    servo_group = ServoGroup(servo_params, switch_servos)
    
    print('initialising servos...')
    servo_group.initialise(servo_init)
    print('servo_group initialised')
    while True:
        sw_states = switch_group.get_states()
        print(sw_states)
        servo_group.match_demand(sw_states)
        sleep_ms(polling_interval)

    
if __name__ == '__main__':
    main()
