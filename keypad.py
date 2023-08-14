""" Read matrix keypad with Pi Pico """

from machine import Pin
import uasyncio as asyncio
import array
from queue import KeyBuffer
from time import ticks_ms


class SwitchMatrix:
    """ matrix of up to 16 x 16 switched nodes
        - data returned as linear array (col, row)
        - array type-codes for unsigned int values:
          'B' 1-byte; 'I' 2-byte; 'L' 4-byte
    """
    
    type_code = 'B'  # single byte unsigned integer
    
    def __init__(self, cols, rows):
        self.col_pins = tuple(
            [Pin(pin, mode=Pin.OUT) for pin in cols])
        self.row_pins = tuple(
            [Pin(pin, mode=Pin.IN, pull=Pin.PULL_DOWN) for pin in rows])
        for pin in self.col_pins:
            pin.low()  # set all columns to off
        self._array_length = len(cols) * len(rows)
        self.matrix = array.array(
            SwitchMatrix.type_code, [0] * self._array_length)

    def scan_matrix(self):
        """ scan matrix nodes """
        index = 0
        for c_pin in self.col_pins:
            c_pin.high()
            for r_pin in self.row_pins:
                self.matrix[index] = r_pin.value()
                index += 1
            c_pin.low()
        return self.matrix

    def __len__(self):
        return self._array_length


class Key:
    """ keypad key-switch """
    
    def __init__(self, char):
        # self.index = index
        self._char = char
        self.state = 0
        self.pressed = False
        self.t_pressed = None

    @property
    def char(self):
        return self._char


class KeyPad(SwitchMatrix):
    """ process matrix keypad input
        - output key-value to Buffer object
        - matrix nodes and key objects matched in (col, row) order
    """
    # (col, row) order
    key_values = ('1', '2', '3', 'A',
                  '4', '5', '6', 'B',
                  '7', '8', '9', 'C',
                  '*', '0', '#', 'D'
                  )

    def __init__(self, cols, rows, buffer):
        super().__init__(cols, rows)
        self.buffer = buffer
        self.key_list = []
        for index in range(self._array_length):
            self.key_list.append(Key(self.key_values[index]))

    async def key_input(self):
        """ coro: detect key-press in switch matrix
                - data producer: put char into buffer
                - no other processing in this demo
        """
        # poll switches
        while True:
            scan_time = ticks_ms()
            matrix_states = self.scan_matrix()
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
        print(f'char: {char} consumed by print_buffer()')


async def main():
    # KeyPad: RPi Pico pin assignments
    cols = (8, 9, 10, 11)
    rows = (12, 13, 14, 15)

    buffer = KeyBuffer()
    kp = KeyPad(cols, rows, buffer)
    asyncio.create_task(print_buffer(buffer))
    await kp.key_input()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
