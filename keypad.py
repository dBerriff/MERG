""" Read matrix keypad with Pi Pico """

from machine import Pin
import uasyncio as asyncio
from queue import KeyBuffer
from time import ticks_ms


class SwitchMatrix:
    """ matrix of up to 16 x 16 switched nodes
        - matrix data returned as linear list index: (row * n_cols + col)
        - switch each matrix row ON and scan each column for input
        - could use array rather than list...
    """
    
    def __init__(self, cols, rows):
        self.col_pins = tuple(
            [Pin(pin, mode=Pin.IN, pull=Pin.PULL_DOWN) for pin in cols])
        self.row_pins = tuple(
            [Pin(pin, mode=Pin.OUT) for pin in rows])
        for pin in self.row_pins:
            pin.low()  # set all rows to off
        self.n_cols = len(cols)
        self.n_rows = len(rows)
        self._array_length = self.n_cols * self.n_rows
        self.m_list = [0] * self._array_length

    def scan_matrix(self):
        """ scan matrix nodes """
        # switch each row input high in sequence
        index = 0
        for r, r_pin in enumerate(self.row_pins):
            r_pin.high()
            for c, c_pin in enumerate(self.col_pins):
                # check each col in sequence for switch closed
                self.m_list[index] = c_pin.value()
                index += 1
            r_pin.low()
        return self.m_list

    def __len__(self):
        return self._array_length


class Key:
    """ keypad key-switch
        - key-press time saved as ticks_ms for future dev
    """
    
    def __init__(self, col, row, char):
        self.col = col
        self.row = row
        self._char = char
        self.state = 0
        self.pressed = False
        self.t_pressed = None

    @property
    def char(self):
        return self._char
    
    def __str__(self):
        return f'col: {self.col}, row: {self.row}, char: {self.char}'


class KeyPad(SwitchMatrix):
    """ process matrix keypad input
        - output key-value to Buffer object
        - matrix nodes and key objects matched in (col, row) order
    """
    # (col, row) order
    key_char_list = ('1', '2', '3', 'A',
                     '4', '5', '6', 'B',
                     '7', '8', '9', 'C',
                     '*', '0', '#', 'D'
                     )

    def __init__(self, cols, rows, buffer):
        super().__init__(cols, rows)
        self.buffer = buffer
        self.key_list = []
        index = 0
        for row in range(self.n_rows):
            for col in range(self.n_cols):
                self.key_list.append(Key(col, row, self.key_char_list[index]))
                index += 1

    async def key_input(self):
        """ coro: detect key-press in switch matrix
                - data producer: put char into buffer
                - no other processing in this demo
        """
        # poll switches
        while True:
            scan_time = ticks_ms()
            matrix_states = self.scan_matrix()
            #print(matrix_states)
            for index in range(len(self)):
                node_state = matrix_states[index]
                key = self.key_list[index]
                if node_state == 1 and key.state == 0:
                    key.state = 1
                    await self.buffer.put(key.char)
                    key.t_pressed = scan_time
                elif key.state == 1 and node_state == 0:
                    key.state = 0
            await asyncio.sleep_ms(200)


async def print_buffer(buffer):
    """ consumer: demonstrate buffered input """
    print('Waiting for keypad input...')
    while True:
        char = await buffer.get()
        print(f'char: {char} from buffer')


async def main():
    # KeyPad: RPi Pico pin assignments
    cols = (12, 13, 14, 15)
    rows = (8, 9, 10, 11)


    buffer = KeyBuffer()
    kp = KeyPad(cols, rows, buffer)
    for key in kp.key_list:
        print(key)
    asyncio.create_task(print_buffer(buffer))
    await kp.key_input()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
