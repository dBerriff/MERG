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
    NS_PER_DEGREE = const(11_111)

    OFF = const(0)
    ON = const(1)

    # short delay period
    PAUSE = const(200)  # ms
    SERVO_WAIT = const(500)  # ms

    def __init__(self, pin, off_deg, on_deg, transition_time=3.0):
        super().__init__(Pin(pin))
        self.freq(ServoSG9x.FREQ)
        self.id = pin
        self.off_ns = self.degrees_to_ns(off_deg)
        self.on_ns = self.degrees_to_ns(on_deg)
        self.transition_ms = int(transition_time * 1000)
        self.state = None
        self.pw_ns = None
        self.x_steps = 100
        self._step_ms = self.transition_ms // self.x_steps
        # self._pw_step_inc = (self.on_ns - self.off_ns) // self.x_steps

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
        self.duty_ns(0)
        sleep_ms(self.SERVO_WAIT)

    def set_on(self):
        """ move direct to on position; set object attributes """
        self.duty_ns(self.on_ns)
        self.pw_ns = self.on_ns
        self.state = self.ON
        sleep_ms(self.SERVO_WAIT)

    async def move_servo(self, demand_pw):
        """ move servo from start_ns to demand_ns """
        pw = self.pw_ns
        inc_ns = (demand_pw - pw) // self.x_steps
        step_pause = self._step_ms  # reduce dict look-ups
        # restore PWM
        self.duty_ns(pw)
        for _ in range(self.x_steps - 1):
            pw += inc_ns
            self.duty_ns(pw)
            await asyncio.sleep_ms(step_pause)
        self.duty_ns(demand_pw)  # precise final setting
        await asyncio.sleep_ms(step_pause)
        self.pw_ns = demand_pw
        # stop PWM
        self.duty_ns(0)
        return self.state  # for testing


class ServoGroup:
    """ create a list of servo objects for servo control
        - index: servo-object
        - switch_servos_ binds each servo to a specific switch input
        - could use the list index to reference a servo, but
        - a dictionary implements a more general approach
    """

    def __init__(self, servo_parameters, buffer):
        self.id_servo = {}
        for pin in servo_parameters:
            servo = ServoSG9x(pin, *servo_parameters[pin])
            self.id_servo[servo.id] = servo
        self.buffer = buffer

    def initialise(self, servo_init_):
        """ initialise servos by servo_init list
            - allows for reading initial states from file
            - set sequentially: avoid start-up current spike?
        """
        for id_ in servo_init_:
            servo = self.id_servo[id_]
            if servo_init_[id_] == servo.ON:
                servo.set_on()
            else:
                servo.set_off()

    async def match_demand(self):
        """ coro: match servo positions to on/off switch demands """
        while True:
            await self.buffer.is_data.wait()
            demand = await self.buffer.pop()
            print(f'match demand: {demand}')
            tasks = []
            for id_ in demand:
                servo = self.id_servo[id_]
                srv_demand = demand[id_]
                if servo.state == srv_demand:
                    continue  # already at demand state
                demand_ns = servo.on_ns if srv_demand == servo.ON else servo.off_ns
                tasks.append(servo.move_servo(demand_ns))
                servo.state = srv_demand  # save new demand state
            await asyncio.gather(*tasks)

    def __str__(self):
        """ print out servo parameters """
        s = ''
        for id_ in self.id_servo:
            servo = self.id_servo[id_]
            s += f'id: {servo.id} off_ns: {servo.off_ns} on_ns: {servo.on_ns} transition_ms {servo.transition_ms}'
        return s


class SwitchGroup:
    """ switch states to set servos """

    def __init__(self, sw_states, switch_servos, data_buffer):
        self.sw_states = sw_states
        self.switch_servos = switch_servos
        self.data_buffer = data_buffer

    def get_servo_demand(self, sw_states_):
        """ return dict- servo_id: demand """
        servo_demand = {}
        for key in sw_states_:
            sw_demand = sw_states_[key]
            for servo_id in self.switch_servos[key]:
                servo_demand[servo_id] = sw_demand
        return servo_demand

    async def run_states(self):
        """ run through a set of switch states """
        for state in self.sw_states:
            demand = self.get_servo_demand(state)
            await self.data_buffer.add(demand)
            await asyncio.sleep_ms(5_000)  # pause between settings


class DataBuffer:
    """ single item buffer
        - similar interface to Queue
        - Event.set() "must be called from within a task"
        - hence add() and pop() as coros
    """

    def __init__(self):
        self._item = None
        self.is_data = asyncio.Event()

    async def add(self, item):
        """ add item to buffer """
        self._item = item
        self.is_data.set()


    async def pop(self):
        """ remove item from buffer """
        self.is_data.clear()
        return self._item


async def main():
    """ test servo operation by applying pre-set demand values """
    print('In main()')

    # parameters: dictionaries used to identify objects

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

    # (simulated) switch test states; id: state
    test_sw_states = (
        {16: 0, 17: 1, 18: 1},
        {16: 1, 17: 0, 18: 0},
        {16: 0, 17: 1, 18: 1},
        {16: 0, 17: 0, 18: 0},
        {16: 1, 17: 1, 18: 1},
        {16: 0, 17: 0, 18: 0}
    )
    # === end of parameters

    buffer = DataBuffer()
    switch_group = SwitchGroup(test_sw_states, switch_servos, buffer)
    servo_group = ServoGroup(servo_params, buffer)
    print('initialising servos...')
    servo_group.initialise(servo_init)
    print('run switch-input test...')
    asyncio.create_task(servo_group.match_demand())
    await switch_group.run_states()
    print('test complete')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
