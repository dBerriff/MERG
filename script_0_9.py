"""
    set servos from test values for switch input
    N.B. Demonstration code: prioritises clarity before efficiency
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

    # notional motion on an x, y graph between points
    # motion from point (0, 0) to (100, 100) in straight-line segments
    # starting point (0, 0) is assumed
    motion_coords = {
        'linear': ((100, 100),),
        'overshoot': ((50, 110), (65, 120), (90, 90), (100, 100)),
        'bounce': ((50, 100), (62, 75), (75, 100), (88, 90), (100, 100)),
        's_curve': ((35, 20), (65, 80), (100, 100)),
        'slowing': ((25, 54), (50, 81), (75, 95), (100, 100))
    }

    def __init__(self, pin, off_deg, on_deg,
                 transition_time=1.0, motion='linear'):
        self.pin = pin  # for diagnostics
        self.off_ns = self.degrees_to_ns(self.deg_in_range(off_deg))
        self.on_ns = self.degrees_to_ns(self.deg_in_range(on_deg))
        self.transition_ms = int(transition_time * 1000)
        if motion in self.motion_coords:
            self.coords = self.motion_coords[motion]
        else:
            self.coords = self.motion_coords['linear']
        self.pwm = PWM(Pin(pin))
        self.pwm.freq(self.FREQ)
        self.pw_ns = None  # for self.activate_pulse()
        self.state = None
        # set servo transition parameters
        self.pw_range = self.on_ns - self.off_ns
        self.x_inc = 1
        self.x_steps = 100
        self.step_ms = self.transition_ms // self.x_steps
        self.pw_off_on_inc = (self.on_ns - self.off_ns) // self.x_steps
        self.pw_on_off_inc = -self.pw_off_on_inc

    def degrees_to_ns(self, degrees):
        """ convert float degrees to int pulse-width ns """
        absolute_degrees = degrees - self.DEG_MIN
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
        if self.PW_MIN <= pw_ <= self.PW_MAX:
            self.pwm.duty_ns(pw_)

    def set_off(self):
        """ move servo direct to off position """
        self.move_servo(self.off_ns)
        self.pw_ns = self.off_ns
        self.state = self.OFF

    def set_on(self):
        """ move servo direct to on position """
        self.move_servo(self.on_ns)
        self.pw_ns = self.on_ns
        self.state = self.ON

    def activate_pulse(self):
        """ turn on PWM output """
        self.move_servo(self.pw_ns)

    def zero_pulse(self):
        """ turn off PWM output """
        self.pwm.duty_ns(0)


    async def transition(self, start_pw, pw_inc, pw_final):
        """ move servo in linear segments """
        coords = self.coords
        step_ms = self.step_ms
        x_inc = self.x_inc
        move_servo = self.move_servo
        x0 = 0
        y0 = 0
        for x1, y1 in coords:
            pw_0 = pw_inc * y0
            pw_1 = pw_inc * y1
            segment_step_pw = (pw_1 - pw_0) // (x1 - x0)
            pw_ = pw_0 + start_pw
            x = x0
            while x < x1:
                x += x_inc
                pw_ += segment_step_pw
                move_servo(pw_)
                await asyncio.sleep_ms(step_ms)
            x0 = x1
            y0 = y1


    async def set_servo_on_off(self, demand_):
        """ move servo between off and on positions """
        # move servo between off and on pulse-widths
        # set parameters
        if demand_ == self.state:
            return
        elif demand_ == self.OFF:
            pw_inc = self.pw_on_off_inc
            final_ns = self.off_ns
        elif demand_ == self.ON:
            pw_inc = self.pw_off_on_inc
            final_ns = self.on_ns
        else:
            return
        # move servo
        self.activate_pulse()
        await self.transition(self.pw_ns, pw_inc, final_ns)
        self.zero_pulse()
        # save final state for next move
        self.pw_ns = final_ns
        self.state = demand_
        return self.state  # for testing


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
                self.servos[pin].set_off_on()
            sleep_ms(500)  # allow movement time
        for servo in self.servos.values():
            servo.duty_ns(0)

    async def match_demand(self, demand: dict):
        """ coro: move each servo to match switch demands """
        # assign tasks elements: avoid creating new list each call
        tasks = self.tasks
        for i, srv_pin in enumerate(demand):
            servo_ = self.servos[srv_pin]
            # coros will not run until awaited
            tasks[i] = servo_.set_on_off(demand[srv_pin])

        # code for 'concurrent' setting
        result = await asyncio.gather(*tasks)
        return result  # for testing
    

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
    servo_params = {0: [45, 135, 5.0, 's_curve'],
                    1: [135, 45, 5.0, 's_curve'],
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
        await asyncio.sleep_ms(1_000)

    
if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
