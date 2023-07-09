"""
    set servos from test values for switch input
    N.B. Demonstration code: prioritises clarity before efficiency
    - servos are set asynchronously
"""

import uasyncio as asyncio  # cooperative multitasking
from machine import Pin, PWM
from time import sleep_ms
import gc  # garbage collection


class ServoSG9x:
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
    PW_CTR = const(1_500_000)
    # set more restrictive values if appropriate
    PW_MIN = const(500_000)  # ns
    PW_MAX = const(2_500_000)  # ns
    # degrees can be offset if preferred
    DEG_MIN = const(0)
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
        self.off_ns = self.degrees_to_ns(off_deg)
        self.on_ns = self.degrees_to_ns(on_deg)
        self.transition_ms = int(transition_time * 1000)
        self.pwm = PWM(Pin(pin))
        self.pwm.freq(self.FREQ)
        self.pw_ns = None  # for self.activate_pulse()
        self.state = None
        # set servo transition parameters
        self.x_steps = 100
        self._step_ms = self.transition_ms // self.x_steps
        self._pw_off_on_inc = (self.on_ns - self.off_ns) // self.x_steps

    def degrees_to_ns(self, degrees):
        """ convert float degrees to int pulse-width ns """
        if degrees < self.DEG_MIN or degrees > self.DEG_MAX:
            return self.PW_CTR
        return int(self.PW_MIN
                   + (degrees - self.DEG_MIN) * self.NS_PER_DEGREE)

    def move_servo(self, pw_):
        """ servo machine.PWM setting method """
        # guard against out-of-range demands
        if self.PW_MIN <= pw_ <= self.PW_MAX:
            self.pwm.duty_ns(pw_)

    def set_off(self):
        """ move direct to off position; set object attributes """
        self.pwm.duty_ns(self.off_ns)
        self.pw_ns = self.off_ns
        self.state = self.OFF

    def set_on(self):
        """ move direct to on position; set object attributes """
        self.pwm.duty_ns(self.on_ns)
        self.pw_ns = self.on_ns
        self.state = self.ON

    def activate_pulse(self):
        """ turn on PWM output """
        self.pwm.duty_ns(self.pw_ns)

    def zero_pulse(self):
        """ turn off PWM output """
        self.pwm.duty_ns(0)

    async def transition(self, pw, pw_inc, pw_final):
        """ move servo in linear steps with step_ms pause """
        pause = self._step_ms
        for _ in range(self.x_steps):
            pw += pw_inc
            self.pwm.duty_ns(pw)
            await asyncio.sleep_ms(pause)
        return pw

    async def set_servo_on_off(self, demand_state):
        """ move servo between off and on positions """

        def print_error(ns_, demand_ns):
            """ testing: print final pulse-width error """
            # check on final setting error as percentage
            error_pc = (ns_ - demand_ns) / demand_ns * 100
            print(f'{self.pin}: pw setting error: {error_pc:.2f}%')

        # set parameters
        if demand_state == self.state:
            return
        elif demand_state == self.OFF:
            inc_ns = -self._pw_off_on_inc
            demand_ns = self.off_ns
        elif demand_state == self.ON:
            inc_ns = self._pw_off_on_inc
            demand_ns = self.on_ns
        else:
            return
        # move servo
        self.activate_pulse()
        pw_ns = await self.transition(self.pw_ns, inc_ns, demand_ns)
        # print_error(pw_ns, demand_ns)
        self.zero_pulse()
        # save final state for next move
        self.pw_ns = demand_ns
        self.state = demand_state
        return self.state  # for testing


class ServoGroup:
    """ create a dictionary of servo objects for servo control
        - pin_number: servo-object
        - switch_servos_ binds each servo to a specific switch input
    """

    def __init__(self, servo_parameters):
        self.servos = {pin: ServoSG9x(pin, *servo_parameters[pin])
                       for pin in servo_parameters}
        self.tasks = [None] * len(self.servos)  # [None, None, ...]

    def initialise(self, servo_init_: dict):
        """ initialise servos by servo_init dict
            - allows for reading initial states from file
            - set sequentially: avoid start-up current spike?
        """
        for servo in self.servos.values():
            pin = servo.pin
            if pin in servo_init_ and servo_init_[pin] == 1:
                servo.set_on()
            else:
                servo.set_off()
            sleep_ms(500)  # allow movement time
            servo.zero_pulse()

    async def match_demand(self, demand: dict):
        """ coro: move each servo to match switch demands """
        # assign tasks elements: avoid creating new list each call
        tasks = self.tasks
        for i, srv_pin in enumerate(demand):
            servo_ = self.servos[srv_pin]
            # coros will not run until awaited
            tasks[i] = servo_.set_servo_on_off(demand[srv_pin])
        result = await asyncio.gather(*tasks)
        return result  # for testing


async def main():
    """ test servo operation from pre-set "switch" values """
    print('In main()')
    
    def dict_str(dictionary):
        """ build dict string with sorted keys
            - MicroPython dicts are not sorted

        """
        keys = list(dictionary.keys())
        keys.sort()
        d_str = '{'
        for key in keys:
            d_str += f'{key}: {dictionary[key]}, '
        d_str = d_str[:-2] + '}'  # remove final ', '
        return d_str

    def get_servo_demand(sw_states_, switch_servos_):
        """ return dict of servo setting demands """
        servo_demand = {}
        for sw_pin_ in sw_states_:
            demand_ = sw_states_[sw_pin_]
            for servo_pin_ in switch_servos_[sw_pin_]:
                servo_demand[servo_pin_] = demand_
        return servo_demand

    # switch states in standard interface dict format
    # switch test states include no-change values
    test_sw_states = ({16: 0, 17: 0, 18: 0},
                      {16: 1, 17: 1, 18: 1},
                      {16: 0, 17: 0, 18: 0},
                      {16: 1, 17: 1, 18: 1},
                      {16: 0, 17: 0, 18: 0},
                      {16: 0, 17: 0, 18: 0},
                      {16: 1, 17: 1, 18: 1},
                      {16: 0, 17: 0, 18: 0})

    # === switch and servo parameters

    # switch_pins = (16, 17, 18)

    # {pin: (off_deg, on_deg)}
    servo_params = {0: [45, 135],
                    1: [135, 45],
                    2: [45, 135],
                    3: [45, 135]
                    }

    servo_init = {0: 0, 1: 0, 2: 1, 3: 1}

    # {switch-pin: (servo-pin, ...), ...}
    switch_servos = {16: [0, 1],
                     17: [2],
                     18: [3]
                     }

    # === end of parameters

    servo_group = ServoGroup(servo_params)
    print('initialising servos...')
    servo_group.initialise(servo_init)
    print('servo_group initialised')
    print('run switch-input test...')
    for sw_states in test_sw_states:
        print()
        print(dict_str(sw_states))
        settings = await servo_group.match_demand(
            get_servo_demand(sw_states, switch_servos))
        print(settings)
        gc.collect()  # garbage collect while not busy
        sleep_ms(2_000)  # simulate operations pause


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
