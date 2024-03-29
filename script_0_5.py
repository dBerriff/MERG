"""
    GPIO switch input and servo control
    N.B. Demonstration code: prioritises clarity before efficiency
    - non-asyncio: servos must be set sequentially
"""

from machine import Pin, PWM
from micropython import const
from time import sleep_ms


class ServoSG9x(PWM):
    """
        control a servo by PWM
        - use Pico PWM hardware and built-in MP library
        - Pico PWM implements 0% to 100% duty cycle inclusive
        - user units are degrees
        - internal units are pulse-width in ns
    """

    FREQ = const(50)  # Hz for SG90 servos

    # motion from approximately 0 to 180 degrees
    # (45 to 135 degrees should be used in practice)
    # corresponding specified pulse widths: 500_000 to 2_500_000 ns
    PW_MIN = const(500_000)  # ns
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

    def __init__(self, pin, off_deg, on_deg, transition_time=3.0):
        super().__init__(Pin(pin))
        self.freq(ServoSG9x.FREQ)
        self.id = pin  # for diagnostics
        self.off_ns = self.degrees_to_ns(self.deg_in_range(off_deg))
        self.on_ns = self.degrees_to_ns(self.deg_in_range(on_deg))
        self.transition_ms = int(transition_time * 1000)
        self.pw_ns = None  # for self.activate_pulse()
        self.state = None
        # set servo transition parameters
        self.pw_range = self.on_ns - self.off_ns
        self.x_inc = 1
        self.x_steps = 100
        self.step_ms = self.transition_ms // self.x_steps

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
        if self.PW_MIN <= pw_ <= self.PW_MAX:
            self.duty_ns(pw_)

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
        """ restore PWM output """
        self.move_servo(self.pw_ns)

    def zero_pulse(self):
        """ hold output at zero """
        self.duty_ns(0)

    def transition(self, pw_demand_ns):
        """ move servo in linear steps with step_ms pause """
        pw = self.pw_ns
        pw_inc = (pw_demand_ns - pw) // self.x_steps
        for _ in range(self.x_steps):
            pw += pw_inc
            self.duty_ns(pw)
            sleep_ms(self.step_ms)

    def set_servo_state(self, demand_):
        """ set servo to demand position off or on """
        if demand_ == self.state:
            return
        elif demand_ == self.OFF:
            final_ns = self.off_ns
        elif demand_ == self.ON:
            final_ns = self.on_ns
        else:
            return

        self.activate_pulse()
        self.transition(final_ns)
        self.zero_pulse()
        # save final state
        self.pw_ns = final_ns
        self.state = demand_


class ServoGroup:
    """ create a dictionary of servo objects for servo control
        - pin_number: servo-object
        - switch_servos_ binds each servo to a specific switch input
    """
    
    def __init__(self, servo_parameters, switch_servos_):
        self.servos = {}
        for pin in servo_parameters:
            self.servos[pin] = ServoSG9x(pin, *servo_parameters[pin])
        self.switch_servos = switch_servos_
        self.switch_list = list(self.switch_servos.keys())
        self.switch_list.sort()
        print(self.switch_list)

    def initialise(self, servo_init_):
        """ initialise servos by servo_init dict
            - allows for reading initial states from file
        """
        for pin in servo_init_:
            if servo_init_[pin] == 1:
                self.servos[pin].set_on()
            else:
                self.servos[pin].set_off()
            sleep_ms(500)  # allow movement time per servo
        for servo in self.servos.values():
            servo.duty_ns(0)
    
    def match_demand(self, switch_states):
        """ set servos from switch_states dictionary """
        # set in key order
        switch_ids = list(switch_states)
        switch_ids.sort()
        for sw in switch_ids:
            demand_state = switch_states[sw]
            for servo_pin in self.switch_servos[sw]:
                self.servos[servo_pin].set_servo_state(demand_state)
    

def main():
    """ test of servo movement """
    # switch states in standard interface dict format
    # switch test states include no-change values
    test_sw_states = ({16: 0, 17: 0, 18: 0},
                      {16: 1, 17: 1, 18: 1},
                      {16: 1, 17: 1, 18: 1},
                      {16: 0, 17: 0, 18: 0},
                      {16: 1, 17: 1, 18: 1},
                      {16: 0, 17: 0, 18: 0})
        
    # === switch and servo parameters
    
    # {pin: (off_deg, on_deg, transition_time)}
    servo_params = {0: [45, 135],
                    1: [135, 45],
                    2: [45, 135],
                    3: [135, 45]
                    }

    servo_init = {0: 0, 1: 0, 2: 0, 3: 0}
    
    # {switch-pin: (servo-pin, ...), ...}
    switch_servos = {16: [0, 1],
                     17: [2],
                     18: [3]
                     }

    # === end of parameters

    # create and initialise ServoGroup object
    servo_group = ServoGroup(servo_params, switch_servos)
    # confirm servo instantiation
    for servo in servo_group.servos.values():
        print(f'servo id: {servo.id}, off_ns: {servo.off_ns}, on_ns: {servo.on_ns}')
    print('initialising servos...')
    servo_group.initialise(servo_init)
    print('servo_group initialised')
    print()
    for sw_states in test_sw_states:
        print(sw_states)
        servo_group.match_demand(sw_states)
    print('test complete')


if __name__ == '__main__':
    main()
