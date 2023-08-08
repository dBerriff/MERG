"""
    set servos with linear segment motion
    N.B. Demonstration code: prioritises clarity before efficiency
    - servos are set asynchronously
"""

import uasyncio as asyncio
from machine import Pin, PWM
from time import sleep_ms
import json
import gc


class ServoSG9x(PWM):
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
    PW_CTR = const(1_500_000)
    PW_MIN = const(500_000)  # ns
    PW_MAX = const(2_500_000)  # ns
    DEG_MIN = const(0)
    DEG_MAX = const(180)
    NS_PER_DEGREE = const((PW_MAX - PW_MIN) // (DEG_MAX - DEG_MIN))

    OFF = const(0)
    ON = const(1)
    
    # short delay period
    PAUSE = const(200)  # ms
    SERVO_WAIT = const(500)  # ms

    # motion: x, y axes; straight line between specified points
    # from point (0, 0) to (100, 100); (0, 0) assumed
    motion_set = {'linear', 'overshoot', 'bounce', 's_curve',
                  'slowing', 'semaphore'}
    motion_coords = {
        'linear': ((100, 100),),
        'overshoot': ((60, 110), (70, 95), (80, 103), (90, 98), (100, 100)),
        'bounce': ((60, 100), (70, 90), (80, 100), (90, 95), (100, 100)),
        's_curve': ((35, 20), (65, 80), (100, 100)),
        'slowing': ((25, 54), (50, 81), (75, 95), (100, 100))
        }

    def __init__(self, pin, off_deg, on_deg,
                 transition_time=3.0, motion='linear'):
        super().__init__(Pin(pin))
        self.freq(self.FREQ)
        self.id = pin  # for diagnostics
        self.off_ns = self.degrees_to_ns(off_deg)
        self.on_ns = self.degrees_to_ns(on_deg)
        self.transition_ms = int(transition_time * 1000)
        if motion not in self.motion_set:
            motion = 'linear'
        if motion == 'semaphore':
            motion_on = 'overshoot'
            motion_off = 'bounce'
        else:
            motion_on = motion
            motion_off = motion
        self.pw_ns = None  # for self.activate_pulse()
        self.state = None
        # set servo transition parameters
        self.pw_range = self.on_ns - self.off_ns
        self.x_inc = 1
        self.x_steps = 100
        self.step_ms = self.transition_ms // self.x_steps
        self.pw_on_inc = (self.on_ns - self.off_ns) // self.x_steps  # per y step
        self.on_coords = self.motion_coords[motion_on]
        self.pw_off_inc = -self.pw_on_inc
        self.off_coords = self.motion_coords[motion_off]

    def degrees_to_ns(self, degrees):
        """ convert float degrees to int pulse-width ns """
        if self.DEG_MIN <= degrees <= self.DEG_MAX:
            return int(self.PW_MIN + (degrees - self.DEG_MIN) * self.NS_PER_DEGREE)
        else:
            return self.PW_CTR
    
    def move_servo(self, pw_):
        """ servo machine.PWM setting method """
        # guard against out-of-range demands
        if self.PW_MIN <= pw_ <= self.PW_MAX:
            self.duty_ns(pw_)

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

    async def stepper(self, start_pw, pw_inc_, coords_):
        """ move servo in linear segments """
        # avoid repeated dict look-ups
        step_ms = self.step_ms
        x_inc = self.x_inc
        move_servo = self.move_servo
        x_0 = 0
        y_0 = 0
        for x1, y1 in coords_:
            pw_0 = pw_inc_ * y_0
            pw_1 = pw_inc_ * y1
            segment_pw_inc = (pw_1 - pw_0) // (x1 - x_0)
            pw_ = pw_0 + start_pw
            x = x_0
            while x < x1:
                x += x_inc
                pw_ += segment_pw_inc
                move_servo(pw_)
                await asyncio.sleep_ms(step_ms)
            x_0 = x1
            y_0 = y1

    async def set_on_off(self, demand_):
        """ move servo between off and on positions """
        # move servo between off and on pulse-widths
        # set parameters
        if demand_ == self.state:
            return
        elif demand_ == self.OFF:
            pw_inc = self.pw_off_inc
            final_ns = self.off_ns
            coords = self.off_coords
        elif demand_ == self.ON:
            pw_inc = self.pw_on_inc
            final_ns = self.on_ns
            coords = self.on_coords
        else:
            return
        # move servo
        self.duty_ns(self.pw_ns)
        await self.stepper(self.pw_ns, pw_inc, coords)
        self.duty_ns(0)
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
                self.servos[pin].set_off()
            sleep_ms(500)  # allow movement time
        for servo in self.servos.values():
            servo.duty_ns(0)

    async def match_demand(self, demand: dict):
        """ coro: move each servo to match switch demands """
        # assign tasks elements: avoid creating new list each call
        tasks = self.tasks
        for i, srv_id in enumerate(demand):
            servo_ = self.servos[srv_id]
            # coros will not run until awaited
            tasks[i] = servo_.move_servo(demand[srv_id])
        # code for 'concurrent' setting
        result = await asyncio.gather(*tasks)
        return result  # for testing
    

async def main():
    """ test servo operation from pre-set "switch" values """
    print('In main()')
    
    def write_servo_params(servo_params_):
        """ write servo paramaeters to local JSON file """
        with open('servo_params.json', 'w') as write_file:
            json.dump(servo_params_, write_file)

    def read_servo_params():
        """ write servo paramaeters to local JSON file """
        with open('servo_params.json', 'r') as read_file:
            data = json.load(read_file)
        return {int(key): data[key] for key in data}

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
    servo_params = {0: [45, 135, 3.0, 's_curve'],
                    1: [135, 45, 3.0, 's_curve'],
                    2: [45, 135, 3.0, 'slowing'],
                    3: [45, 135, 2.0, 'semaphore']
                    }

    servo_init = {0: 0, 1: 0, 2: 0, 3: 0}
    
    # {switch-pin: (servo-pin, ...), ...}
    switch_servos = {16: [0, 1],
                     17: [2],
                     18: [3]
                     }

    # === end of parameters
    
    write_servo_params(servo_params)
    
    servo_params = read_servo_params()
    print(servo_params)

    servo_group = ServoGroup(servo_params)
    print('initialising servos...')
    servo_group.initialise(servo_init)
    print('servo_group initialised')
    for sw_states in test_sw_states:
        print(sw_states)
        settings = await servo_group.match_demand(
            get_servo_demand(sw_states, switch_servos))
        print(settings)
        gc.collect()
        await asyncio.sleep_ms(1_000)

    
if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
