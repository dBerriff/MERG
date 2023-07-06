"""
    set servos from test values for switch input
    - servos are set asynchronously
"""

import uasyncio as asyncio
from machine import Pin, PWM
from time import sleep_ms


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
        self.pw_ns = None  # for self.activate_pulse()
        self.state = None
        # set servo transition parameters
        self.pw_range = self.on_ns - self.off_ns
        self.x_inc = 1
        self.x_steps = 100
        self.step_ms = self.transition_ms // self.x_steps

    def degrees_to_ns(self, degrees):
        """ convert float degrees to int pulse-width ns """
        absolute_degrees = degrees - self.DEG_MIN
        print(absolute_degrees)
        return int(self.PW_MIN
                   + absolute_degrees * self.NS_PER_DEGREE)
    
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
        self.pw_ns = self.off_ns
        self.state = self.OFF

    def set_on(self):
        """ set servo direct to on position """
        self.move_servo(self.on_ns)
        self.pw_ns = self.on_ns
        self.state = self.ON

    def activate_pulse(self):
        """ turn on PWM output """
        self.move_servo(self.pw_ns)

    def zero_pulse(self):
        """ turn off PWM output """
        self.pwm.duty_ns(0)

    async def transition(self, pw, pw_inc, steps_, step_ms):
        """ move servo in linear steps with step_ms pause """
        for _ in range(steps_):
            pw += pw_inc
            self.move_servo(pw)
            await asyncio.sleep_ms(step_ms)

    async def set_servo_state(self, demand_):
        """ set servo to demand position off or on """
        # set parameters
        if demand_ == self.state:
            return
        elif demand_ == self.OFF:
            pw_inc = (self.off_ns - self.pw_ns) // self.x_steps
            final_ns = self.off_ns
        elif demand_ == self.ON:
            pw_inc = (self.on_ns - self.pw_ns) // self.x_steps
            final_ns = self.on_ns
        else:
            return
        # move servo
        self.activate_pulse()
        await self.transition(
            self.pw_ns, pw_inc, self.x_steps, self.step_ms)
        # final pause for servo transition - necessary?
        await asyncio.sleep_ms(200)
        self.zero_pulse()
        # save final state for next move
        self.pw_ns = final_ns
        self.state = demand_
        return self.state


class ServoGroup:
    """ create a dictionary of servo objects for servo control
        - pin_number: servo-object
        - switch_servos_ binds each servo to a specific switch input
    """
    
    def __init__(self, servo_parameters):
        self.servos = {pin: ServoSG9x(pin, *servo_parameters[pin])
                       for pin in servo_parameters}
        self.tasks = [None] * len(self.servos)

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

    async def match_demand(self, demand: dict):
        """ coro: move each servo to match switch demands """
        # assign tasks elements: avoid creating new list each call
        tasks = self.tasks
        for i, srv_pin in enumerate(demand):
            servo_ = self.servos[srv_pin]
            tasks[i] = servo_.set_servo_state(demand[srv_pin])
        result = await asyncio.gather(*tasks)
        # for testing
        return result


async def main():
    """ test servo operation from pre-set "switch" values """
    print('In main()')

    def get_servo_demand(sw_states_, switch_servos_):
        """ return dict of servo setting demands """
        servo_demand = {}
        for sw_pin_ in sw_states_:
            demand_ = sw_states_[sw_pin_]
            for servo_pin_ in switch_servos_[sw_pin_]:
                servo_demand[servo_pin_] = demand_
        return servo_demand

    print('In main()')

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
    servo_params = {0: [70, 110],
                    1: [110, 70],
                    2: [45, 135],
                    3: [45, 135]
                    }

    servo_init = {0: 0, 1: 0, 2: 0, 3: 0}
    
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
    for sw_states in test_sw_states:
        print(sw_states)
        settings = await servo_group.match_demand(
            get_servo_demand(sw_states, switch_servos))
        print(settings)
        await asyncio.sleep_ms(2_000)

    
if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
