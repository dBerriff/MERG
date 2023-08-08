"""
    set servos and relays from test values for switch input
    N.B. Demonstration code: prioritises clarity before efficiency
    - servos and relays are set asynchronously
"""

import uasyncio as asyncio
from machine import Pin, PWM
from time import sleep_ms
import gc


class ServoSG9x(PWM):
    """ control a servo by PWM
        - user units are degrees
        - internal units are pulse-width in ns
          (servos usually specified by pulse-width)
    """

    # SG90 servos specify f = 50Hz
    FREQ = const(50)  # Hz

    # specified servo motion is from 45 to 135 degrees
    # corresponding pulse widths: 1_000_000 to 2_000_000 ns
    DEG_MIN = const(0)
    DEG_MAX = const(90)
    PW_MIN = const(1_000_000)  # ns
    PW_CTR = const(1_500_000)
    PW_MAX = const(2_000_000)
    NS_PER_DEGREE = const((PW_MAX - PW_MIN) // (DEG_MAX - DEG_MIN))

    OFF = const(0)
    ON = const(1)

    # short delay period
    PAUSE = const(200)  # ms
    SERVO_WAIT = const(500)  # ms

    # motion: x, y axes; straight line between specified points
    # from point (0, 0) to (100, 100); (0, 0) assumed

    motion_coords = {
        'linear': ((100, 100),),
        'overshoot': ((60, 110), (70, 95), (80, 105), (90, 95), (100, 100)),
        'bounce': ((60, 100), (70, 90), (80, 100), (90, 95), (100, 100)),
        's_curve': ((35, 20), (65, 80), (100, 100)),
        'slowing': ((10, 30), (20, 55), (40, 79), (60, 91), (80, 97), (100, 100))
    }
    # also 'semaphore' for signal "bounce"

    def __init__(self, pin, off_deg, on_deg,
                 transition_period=3.0, motion='linear'):
        super().__init__(Pin(pin))
        self.freq(self.FREQ)
        self.id = pin  # for diagnostics
        self.off_ns = self.degrees_to_ns(off_deg)
        self.on_ns = self.degrees_to_ns(on_deg)
        self.transition_ms = int(transition_period * 1000)
        self.pw_ns = None  # for self.activate_pulse()
        self.state = None
        # set servo (x, y) transition parameters
        self.pw_range = self.on_ns - self.off_ns
        self.x_inc = 1
        self.x_steps = 100
        self.step_ms = self.transition_ms // self.x_steps
        self.pw_on_inc = (self.on_ns - self.off_ns) // self.x_steps  # per y step
        self.pw_off_inc = -self.pw_on_inc
        # set motion parameters
        if motion == 'semaphore':
            motion_on = 'overshoot'
            motion_off = 'bounce'
        else:
            motion_on = motion
            motion_off = motion
        self.on_coords = self.motion_coords[motion_on]
        self.off_coords = self.motion_coords[motion_off]
        # relay object must be assigned if required
        self.relay = None

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
        # local vars avoid repeated dictionary look-ups
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
        return pw_

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

        # relay object must be assigned to servo object if required
        # delay for 50% transition time
        if self.relay:
            # noinspection PyAsyncCall
            asyncio.create_task(
                self.relay.set_state(demand_, self.transition_ms//2))
        # restore pulse (not essential) and move servo
        self.duty_ns(self.pw_ns)
        sw_ns = await self.stepper(self.pw_ns, pw_inc, coords)
        # check for software setting error
        print(f'{final_ns} {sw_ns} {(sw_ns - final_ns) / final_ns * 100:.2f}%')
        # switch off pulse
        self.duty_ns(0)
        # save final state
        self.pw_ns = final_ns
        self.state = demand_
        return self.state  # for testing


class ServoGroup:
    """ create a dictionary of servo objects for servo control
        - pin_number: servo-object
        - switch_servos_ binds each servo to a specific switch input
    """
    # kwargs for 'optional extras' parameters: relays in this case
    def __init__(self, servo_parameters, **kwargs):
        servos = {pin: ServoSG9x(pin, *servo_parameters[pin])
                  for pin in servo_parameters}
        # if relays are specified, add to servo objects
        if 'servo_relay' in kwargs:
            s_r = kwargs['servo_relay']
            for pin in servos:
                # not all servos will have an associated relay
                if pin in s_r:
                    servos[pin].relay = Relay(s_r[pin])
        self.servos = servos
        # task list: avoid creating new list for each method call
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
        tasks = self.tasks
        for i, srv_id in enumerate(demand):
            servo_ = self.servos[srv_id]
            tasks[i] = servo_.move_servo(demand[srv_id])
        # run tasks
        result = await asyncio.gather(*tasks)
        return result  # for testing


class Relay(Pin):
    """ pin out to set a relay """

    def __init__(self, pin):
        super().__init__(pin, Pin.OUT)
        self.pin = pin  # for diagnostics

    async def set_state(self, demand, delay):
        """ set relay pin-out after delay ms """
        # delay: normally half servo transit-time
        await asyncio.sleep_ms(delay)
        self.value(demand)


def get_servo_demand(sw_states_, switch_servos_):
    """ return dict of servo setting demands """
    servo_demand = {}
    for sw_pin_ in sw_states_:
        demand_ = sw_states_[sw_pin_]
        for servo_pin_ in switch_servos_[sw_pin_]:
            servo_demand[servo_pin_] = demand_
    return servo_demand


async def main():
    """ test servo operation from pre-set "switch" values """
    print('In main()')

    # switch test states
    test_sw_states = ({16: 0, 17: 0, 18: 0},
                      {16: 1, 17: 1, 18: 1},
                      {16: 0, 17: 0, 18: 0},
                      {16: 0, 17: 0, 18: 0},
                      {16: 1, 17: 1, 18: 1},
                      {16: 0, 17: 0, 18: 0})

    # === switch and servo parameters

    # switch_pins = (16, 17, 18)

    # {pin: (off_deg, on_deg, transition_period, motion)}
    servo_params = {0: [0, 90, 5.0, 's_curve'],
                    1: [90, 0, 5.0, 's_curve'],
                    2: [0, 90, 5.0, 'slowing'],
                    3: [25, 70, 2.0, 'semaphore']
                    }

    servo_init = {0: 0, 1: 0, 2: 0, 3: 0}  # servo-pin: init value
    
    servo_relay = {0: 8, 1: 9, 2: 10}  # servo-pin: relay pin if any

    # {switch-pin: [servo-pin, ...], ...}
    switch_servos = {16: [0, 1],
                     17: [2],
                     18: [3]
                     }

    # === end of parameters

    servo_group = ServoGroup(servo_params, servo_relay=servo_relay)
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
