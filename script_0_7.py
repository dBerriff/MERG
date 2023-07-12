"""
    set servos from test values for switch input
    N.B. Demonstration code: prioritises clarity before efficiency
    - servos are set asynchronously
    - use object ids rather than pins as keys
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

    _id = 0  # unique id for each servo
    
    # SG90 servos specify f = 50Hz
    FREQ = const(50)  # Hz

    # specified servo motion is from approximately 0 to 180 degrees
    # (45 to 135 degrees should be used in practice)
    # corresponding specified pulse widths: 500_000 to 2_500_000 ns
    PW_CTR = const(1_500_000)
    PW_MIN = const(500_000)  # ns
    PW_MAX = const(2_500_000)  # ns
    DEG_MIN = const(0)  # degrees can be offset
    DEG_MAX = const(180)

    NS_PER_DEGREE = const((PW_MAX - PW_MIN) // (DEG_MAX - DEG_MIN))

    OFF = const(0)
    ON = const(1)

    # short delay period
    MIN_WAIT = const(200)  # ms
    SET_WAIT = const(500)  # ms

    def __init__(self, pin, off_deg, on_deg, transition_time=1.0):
        self.pwm = PWM(Pin(pin))
        self.pwm.freq(self.FREQ)
        self.off_ns = self.degrees_to_ns(off_deg)
        self.on_ns = self.degrees_to_ns(on_deg)
        self.transition_ms = int(transition_time * 1000)

        self.id = ServoSG9x._id
        ServoSG9x._id += 1

        self.pw_ns = None
        self.state = None

        self.x_steps = 100
        self._step_ms = self.transition_ms // self.x_steps
        self._pw_off_on_inc = (self.on_ns - self.off_ns) // self.x_steps

    def degrees_to_ns(self, degrees):
        """ convert float degrees to int pulse-width ns """
        if degrees < self.DEG_MIN or degrees > self.DEG_MAX:
            return self.PW_CTR
        return int(self.PW_MIN
                   + (degrees - self.DEG_MIN) * self.NS_PER_DEGREE)

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

    async def transition(self, pw, pw_inc):
        """ move servo in linear steps with step_ms pause """
        pause = self._step_ms
        for _ in range(self.x_steps):
            pw += pw_inc
            self.pwm.duty_ns(pw)
            await asyncio.sleep_ms(pause)
        return pw

    async def set_servo_on_off(self, demand_state):
        """ move servo between off and on positions """

        def error_pc_str(ns_, demand_ns_):
            """ testing: return final pulse-width error as % """
            error_pc = (ns_ - demand_ns_) / demand_ns_ * 100
            return f'{self.id}: pw setting error: {error_pc:.2f}%'

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
        transition_ns = await self.transition(self.pw_ns, inc_ns)
        print(error_pc_str(transition_ns, demand_ns))
        self.zero_pulse()
        # save final state for next move
        self.pw_ns = demand_ns
        self.state = demand_state
        return self.state  # for testing


class ServoGroup:
    """ create a list of servo objects for servo control
        - index: servo-object
        - switch_servos_ binds each servo to a specific switch input
    """

    def __init__(self, servo_pins, servo_parameters):
        self.servos = []
        self.id_servo = {}
        self.id_pin = {}
        for i, pin in enumerate(servo_pins):
            servo = ServoSG9x(pin, *servo_parameters[i])
            self.servos.append(servo)
            self.id_servo[servo.id] = servo
            self.id_pin[servo.id] = pin  # for diagnostics
        print(self.servos)
        print(self.id_servo)
        print(self.id_pin)

    def initialise(self, servo_init_):
        """ initialise servos by servo_init list
            - allows for reading initial states from file
            - set sequentially: avoid start-up current spike?
        """
        for i, setting in enumerate(servo_init_):
            servo = self.servos[i]
            if setting == 1:
                servo.set_on()
            else:
                servo.set_off()
            sleep_ms(500)  # allow movement time
            servo.zero_pulse()

    async def match_demand(self, demand):
        """ coro: move each servo to match switch demands """
        tasks = []
        for id_, setting in demand.items():
            tasks.append(
                self.id_servo[id_].set_servo_on_off(setting))
        result = await asyncio.gather(*tasks)
        return result  # for testing


async def main():
    """ test servo operation by applying pre-set demand values """
    print('In main()')

    def get_servo_demand(sw_states_, switch_servos_):
        """ return dict of servo setting demands """
        servo_demand = {}
        for i, sw_demand in enumerate(sw_states_):
            for servo_index in switch_servos_[i]:
                servo_demand[servo_index] = sw_demand
        return servo_demand

    # switch states by switch id
    # switch test states include no-change values
    test_sw_states = ([0, 0, 0],
                      [1, 1, 1],
                      [0, 0, 0],
                      [1, 1, 1],
                      [0, 0, 0],
                      [0, 0, 0],
                      [1, 1, 1],
                      [0, 0, 0]
                      )

    # === switch and servo parameters
    
    servo_pins = (0, 1, 2, 3)
    
    servo_params = ([45, 135], [135, 45], [45, 135], [45, 135])

    servo_init = (0, 0, 1, 1)

    # {switch-pin: (servo-pin, ...), ...}
    switch_servos = {0: [0, 1],
                     1: [2],
                     2: [3]
                     }

    # === end of parameters

    servo_group = ServoGroup(servo_pins, servo_params)
    print('initialising servos...')
    servo_group.initialise(servo_init)
    print('servo_group initialised')
    print('run switch-input test...')
    for sw_states in test_sw_states:
        print()
        demand = get_servo_demand(sw_states, switch_servos)
        print(demand)
        settings = await servo_group.match_demand(demand)
        print(settings)
        gc.collect()  # garbage collect while not busy
        sleep_ms(2_000)  # simulate operations pause


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
