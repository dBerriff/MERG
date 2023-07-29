"""
    set servos from switch input test values
    - servos are set asynchronously
    - servo pins provide unique id's
"""

import uasyncio as asyncio  # cooperative multitasking
from machine import Pin, PWM
from time import sleep_ms
import gc  # garbage collection


class ServoSG9x(PWM):
    """
        control a servo by PWM
        - class control parameter is pulse-width in nanoseconds
        - user units: degrees
    """
    # SG90 servos specify f = 50Hz
    FREQ = const(50)  # Hz

    # specified servo motion is from 0 to 180 degrees
    # corresponding pulse widths: 500_000 to 2_500_000 ns
    PW_CTR = const(1_500_000)
    PW_MIN = const(500_000)  # ns
    PW_MAX = const(2_500_000)  # ns
    DEG_MIN = const(0)  # include for offset degrees
    DEG_MAX = const(180)
    NS_PER_DEGREE = const((PW_MAX - PW_MIN) // (DEG_MAX - DEG_MIN))

    OFF = const(0)
    ON = const(1)

    # short delay period
    MIN_WAIT = const(200)  # ms
    SERVO_WAIT = const(500)  # ms

    def __init__(self, pin, off_deg, on_deg, transition_time=3.0):
        super().__init__(Pin(pin))
        self.freq(ServoSG9x.FREQ)
        self.id = pin
        self.off_ns = self.degrees_to_ns(off_deg)
        self.on_ns = self.degrees_to_ns(on_deg)
        self.transition_ms = int(transition_time * 1000)
        # for pulse restoration
        self.pw_ns = None
        self.state = None
        # for servo "stepper" algorithm
        self.x_steps = 100
        self._step_ms = self.transition_ms // self.x_steps
        self._pw_step_inc = (self.on_ns - self.off_ns) // self.x_steps

    def degrees_to_ns(self, degrees):
        """ convert float degrees to int pulse-width ns """
        if self.DEG_MIN <= degrees <= self.DEG_MAX:
            return int(self.PW_MIN + (degrees - self.DEG_MIN) * self.NS_PER_DEGREE)
        else:
            return self.PW_CTR

    def set_off(self):
        """ move direct to off position; set object attributes """
        self.duty_ns(self.off_ns)
        self.pw_ns = self.off_ns
        self.state = self.OFF

    def set_on(self):
        """ move direct to on position; set object attributes """
        self.duty_ns(self.on_ns)
        self.pw_ns = self.on_ns
        self.state = self.ON

    async def stepper(self, pw_inc):
        """ move servo in linear steps with pause ms per step """
        pw = self.pw_ns
        pause = self._step_ms
        for _ in range(self.x_steps):
            pw += pw_inc
            self.duty_ns(pw)
            await asyncio.sleep_ms(pause)

    async def set_on_off(self, demand_state):
        """ move servo to off or on position """
        # set parameters
        if demand_state == self.state:
            return
        elif demand_state == self.OFF:
            inc_ns = -self._pw_step_inc
            demand_ns = self.off_ns
        elif demand_state == self.ON:
            inc_ns = self._pw_step_inc
            demand_ns = self.on_ns
        else:
            return
        # move servo
        self.duty_ns(self.pw_ns)  # optional
        await self.stepper(inc_ns)
        self.duty_ns(0)
        # save final state for next move
        self.pw_ns = demand_ns
        self.state = demand_state
        return self.state  # for testing


class ServoGroup:
    """ create a list of servo objects for servo control
        - index: servo-object
        - switch_servos_ binds each servo to a specific switch input
        - could use the list index to reference a servo, but
        - a dictionary implements a more general approach
    """

    def __init__(self, servo_parameters):
        self.id_servo = {}
        for pin in servo_parameters:
            servo = ServoSG9x(pin, *servo_parameters[pin])
            self.id_servo[servo.id] = servo

    def initialise(self, servo_init_):
        """ initialise servos by servo_init list
            - allows for reading initial states from file
            - set sequentially: avoid start-up current spike?
        """
        for id_ in servo_init_:
            servo = self.id_servo[id_]
            if servo_init_[id_] == 1:
                servo.set_on()
            else:
                servo.set_off()
            sleep_ms(500)  # allow movement time
            servo.duty_ns(0)

    async def match_demand(self, demand):
        """ coro: move each servo to match switch demands """
        # asyncio.gather(): awaits completion of all tasks
        tasks = []
        for id_, setting in demand.items():
            tasks.append(self.id_servo[id_].set_on_off(setting))
        result = await asyncio.gather(*tasks)
        return result  # for testing

    def __str__(self):
        """ print out servo parameters """
        s = ''
        for id_ in self.id_servo:
            servo = self.id_servo[id_]
            s += f'id: {servo.id} off_ns: {servo.off_ns} on_ns: {servo.on_ns} transition_ms {servo.transition_ms}'
        return s


async def main():
    """ test servo operation by applying pre-set demand values """
    print('In main()')

    def get_servo_demand(sw_states_, switch_servos_):
        """ return dict; servo_id: demand """
        servo_demand = {}
        for key in sw_states_:
            sw_demand = sw_states_[key]
            for servo_id in switch_servos_[key]:
                servo_demand[servo_id] = sw_demand
        return servo_demand

    # parameters: dictionaries used to identify objects

    # (simulated) switch test states; id: state
    test_sw_states = (
        {16: 0, 17: 1, 18: 1},
        {16: 1, 17: 0, 18: 0},
        {16: 0, 17: 1, 18: 1},
        {16: 1, 17: 0, 18: 0},
        {16: 0, 17: 1, 18: 1},
        {16: 0, 17: 0, 18: 0},
        {16: 1, 17: 1, 18: 1},
        {16: 0, 17: 0, 18: 0}
    )

    # === switch and servo parameters

    # pin: (off_degrees, on_degrees [, transition_time])
    servo_params = {0: (45, 135),
                    1: (135, 45),
                    2: (45, 135),
                    3: (135, 45)
                    }

    servo_init = {0: 0, 1: 0, 2: 0, 3: 0}

    # {switch-pin: [servo-id, ...], ...}
    switch_servos = {16: [0, 1],
                     17: [2],
                     18: [3]
                     }

    # === end of parameters

    servo_group = ServoGroup(servo_params)
    print(servo_group)
    print('initialising servos...')
    servo_group.initialise(servo_init)
    print('run switch-input test...')
    for sw_states in test_sw_states:
        demand = get_servo_demand(sw_states, switch_servos)
        print(f'servo demand: {demand}')
        settings = await servo_group.match_demand(demand)
        print(f'gather return: {settings}')
        gc.collect()  # garbage collect while not busy
        sleep_ms(2_000)  # pause between settings
    print('test complete')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
