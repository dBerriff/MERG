""" Read matrix keypad with Pi Pico """

from machine import Pin
import uasyncio as asyncio


class SwitchMatrix:
    """ matrix with switched nodes """
    
    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows

        # Set col pins as inputs, row pins as outputs
        self.col_pins = tuple(
            [Pin(pin, mode=Pin.OUT) for pin in cols])
        self.row_pins = tuple(
            [Pin(pin, mode=Pin.IN, pull=Pin.PULL_DOWN) for pin in rows])
        for pin in self.col_pins:
            pin.low()

    def scan(self):
        """ scan for closed matrix switch """
        for col, c_pin in enumerate(self.col_pins):
            c_pin.high()
            for row, r_pin in enumerate(self.row_pins):
                if r_pin.value():
                    c_pin.low()
                    return (col << 4) + row
            c_pin.low()
        return None

    def scan_all(self):
        """ scan for all closed matrix switches as list """
        closed_list = []
        for col, c_pin in enumerate(self.col_pins):
            c_pin.high()
            for row, r_pin in enumerate(self.row_pins):
                if r_pin.value():
                    closed_list.append((col << 4) + row)
            c_pin.low()
        return closed_list

    def scan_matrix(self):
        """ scan for all switch states as dictionary """
        matrix_state = {}
        for col, c_pin in enumerate(self.col_pins):
            c_pin.high()
            for row, r_pin in enumerate(self.row_pins):
                matrix_state[(col << 4) + row] = r_pin.value()
            c_pin.low()
        return matrix_state


class KeyPad(SwitchMatrix):
    """ process input from common membrane keypad """
    key_values = {0: '1', 1: '2', 2: '3', 3: 'A',
                  16: '4', 17: '5', 18: '6', 19: 'B',
                  32: '7', 33: '8', 34: '9', 35: 'C',
                  48: '*', 49: '0', 50: '#', 51: 'D'}

    def __init__(self, cols, rows):
        super().__init__(cols, rows)
        self.cols = cols
        self.rows = rows

    async def keypad_input(self):
        """ process single-key input """

        new_press = True
        while True:
            node = self.scan()
            if node is None:
                new_press = True
            elif new_press:
                print(f'node: {node} key: {self.key_values[node]}')
                new_press = False
            await asyncio.sleep_ms(200)


async def main():
    # RPi Pico pin assignments
    cols = (8, 9, 10, 11)
    rows = (12, 13, 14, 15)

    kp = KeyPad(cols, rows)
    await kp.keypad_input()
    """keypad = KeyPad(cols, rows)
    await keypad.poll_keypad()"""


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
