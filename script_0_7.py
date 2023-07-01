"""
    set servos from switch input
    - servos are set asynchronously
"""

import uasyncio as asyncio
from machine import Pin, PWM
from time import sleep_ms
from script_0_3 import HwSwitchGroup


class ServoSG90:
    """ control a servo by PWM
        - user units are degrees
        - internal units are pulse-width in ns
          (servos usually specified by pulse-width)
    """

    # SG90 servos specify f = 50Hz
    FREQ = const(50)  # Hz

    # specified servo motion is from approximately 0 to 180 degrees
    # (45 to 135 degrees should be used in practice)
    # corresponding specified pulse widths: 500_000 to 2_500_000 ns
    # set more restrictive values if appropriate
    PW_MIN = const(500_000)  # ns
    PW_CTR = const(1_500_000)
    PW_MAX = const(2_500_000)  # ns
    DEG_MIN = const(0)
    DEG_CTR = const(90)
    DEG_MAX = const(180)
    
    # conversion factor ns per degree
    NS_PER_DEGREE = const((PW_MAX - PW_MIN) // (DEG_MAX - DEG_MIN))
    # demand states
    OFF = const(0)
    ON = const(1)
    
    # short delay period
    MIN_WAIT = const(200)  # ms
    SET_WAIT = const(500)  # ms

    def __init__(self, pin, off_deg, on_deg, transition_time=1.0):
        self.pin = pin  # for diagnostics
        self.off_ns = self.degrees_to_ns(self.deg_in_range(off_deg))
        self.on_ns = self.degrees_to_ns(self.deg_in_range(on_deg))
        self.transition_ms = int(transition_time * 1000)
        self.pwm = PWM(Pin(pin))
        self.pwm.freq(self.FREQ)
        self.pw = None  # for self.activate_pulse()
        self.state = None
        # set servo transition parameters
        self.pw_range = self.on_ns - self.off_ns
        self.x_inc = 1
        self.x_steps = 100
        self.step_ms = self.transition_ms // self.x_steps
        self.step_pw = self.pw_range // self.x_steps

    def degrees_to_ns(self, degrees):
        """ convert float degrees to int pulse-width ns """
        return int(self.PW_MIN + degrees * self.NS_PER_DEGREE)
    
    def deg_in_range(self, degrees_):
        """ return value within allowed range """
        if self.DEG_MIN <= degrees_ <= self.DEG_MAX:
            value = degrees_
        else:
            value = self.DEG_CTR
        return value

    def move_servo(self, pw_):
        """ servo machine.PWM setting method """
        # guard against out-of-range demands
        # ? remove guard following testing ?
        if self.PW_MIN <= pw_ <= self.PW_MAX:
            self.pwm.duty_ns(pw_)

    def set_off(self):
        """ set servo direct to off position """
        self.move_servo(self.off_ns)
        self.pw = self.off_ns
        self.state = self.OFF

    def set_on(self):
        """ set servo direct to on position """
        self.move_servo(self.on_ns)
        self.pw = self.on_ns
        self.state = self.ON

    def activate_pulse(self):
        """ turn on PWM output """
        self.move_servo(self.pw)

    def zero_pulse(self):
        """ turn off PWM output """
        self.pwm.duty_ns(0)

    async def transition(self, demand_state_):
        """ move servo in linear steps over transition time """
        if demand_state_ == self.state:
            return
        elif demand_state_ == self.ON:
            pw = self.off_ns
            pw_inc = self.step_pw
            set_demand = self.set_on  # method pointer
        elif demand_state_ == self.OFF:
            pw = self.on_ns
            pw_inc = -self.step_pw
            set_demand = self.set_off  # method pointer
        else:
            return

        self.activate_pulse()
        x = 0
        while x < 100:
            x += self.x_inc
            pw += pw_inc
            self.move_servo(pw)
            await asyncio.sleep_ms(self.step_ms)
        # set final position
        set_demand()  # call setting method
        # allow for final rotation
        await asyncio.sleep_ms(self.SET_WAIT)
        self.zero_pulse()
        return self.state  # for asyncio.gather()


class ServoGroup:
    """ create a dictionary of servo objects for servo control
        - pin_number: servo-object
        - switch_servos_ binds each servo to a specific switch input
    """
    
    def __init__(self, servo_parameters, switch_servos_):
        self.servos = {pin: ServoSG90(pin, *servo_parameters[pin])
                       for pin in servo_parameters}
        self.switch_servos = switch_servos_

    def initialise(self, servo_init_: dict):
        """ initialise servos by servo_init dict
            - allows for reading initial states from file
            - not async: avoid start-up current spike
        """
        for pin in servo_init_:
            if servo_init_[pin] == 1:
                self.servos[pin].set_on()
            else:
                self.servos[pin].set_off()
            sleep_ms(500)  # allow movement time
        for servo in self.servos.values():
            servo.zero_pulse()
    
    async def update_linear(self, demand: dict):
        """ coro: move each servo to match switch demands """
        tasks = []  # list for gathered tasks
        for srv_pin in demand:
            servo_ = self.servos[srv_pin]
            tasks.append(servo_.transition(demand[srv_pin]))
        result = await asyncio.gather(*tasks)
        return result


async def main():
    """ module run-time code """

    print('In main()')

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
            # build dict servo_pin: demand
            for sw_pin in switch_pins:
                demand = sw_states[sw_pin]
                for servo_pin in switch_servos[sw_pin]:
                    servo_demand[servo_pin] = demand
            result = await servo_group.update_linear(servo_demand)
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
