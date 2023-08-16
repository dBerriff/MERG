"""
    Read matrix keypad with Pi Pico
    Generic keypad supplied as component in Elegoo kit.
    Simple "membrane" switches close at each column-to-row intersection
        1-2-3-A
        4-5-6-B
        7-8-9-C
        *-0-#-D
    With connections numbered from 0, left-to-right;
    Elegoo diagram shows:
    0:  1-2-3-A  Rows
    1:  4-5-6-B
    2:  7-8-9-C
    3:  *-0-#-D
    4:  1-4-7-*  Cols
    5:  2-5-8-0
    6:  3-6-9-#
    7:  A-B-C-D
    In code, coordinate order is (col, row), as for (x, y)
"""

from machine import Pin
import uasyncio as asyncio
from queue import KeyBuffer
from time import ticks_ms


class SwitchMatrix:
    """ matrix of switched nodes
        - matrix data returned as linear list index: index = (row * n_cols + col)
        - switch each matrix row ON and scan each column for input
        - m_list as list; array gives marginal benefits, if any
    """
    
    def __init__(self, cols, rows):
        # columns are scanned inputs; rows are set high in sequence
        self.col_pins = [Pin(pin, mode=Pin.IN, pull=Pin.PULL_DOWN) for pin in cols]
        self.row_pins = [Pin(pin, mode=Pin.OUT, value=0) for pin in rows]
        # matrix scanned with (col, row) coordinates
        self.n_cols = len(cols)
        self.n_rows = len(rows)
        # list maintains correspondence between matrix and switch states
        self._list_len = self.n_cols * self.n_rows
        self.m_list = [0] * self._list_len

    def scan_matrix(self):
        """ scan matrix nodes """
        # switch each row output high in sequence
        # then scan each col for input
        index = 0
        for r_pin in self.row_pins:
            r_pin.high()
            for c_pin in self.col_pins:
                self.m_list[index] = c_pin.value()
                index += 1
            r_pin.low()
        return self.m_list

    def __len__(self):
        return self._list_len


class KeyPad(SwitchMatrix):
    """ process SwitchMatrix as matrix of Key objects
        - output key-value to Buffer object
        - matrix nodes and key objects matched in (col, row) order
        - intention is that:
          modifier keys, hold or press, ...
          will be processed in this class or Key class
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
        # maintain correspondence between m_list and key list
        self.key_list = []
        index = 0
        # dict for future processing
        self.char_key = {}
        for row in range(self.n_rows):
            for col in range(self.n_cols):
                key = Key(self.key_char_list[index])
                self.key_list.append(key)
                index += 1
                self.char_key[key.char] = key

    async def key_input(self):
        """ coro: detect key-press in switch matrix
                - data producer: put char into buffer
        """
        # poll switches
        while True:
            scan_time = ticks_ms()
            matrix_states = self.scan_matrix()
            # print(matrix_states)
            for index in range(len(self)):
                node_state = matrix_states[index]
                key = self.key_list[index]
                if node_state == 1 and key.state == 0:
                    key.state = 1
                    await self.buffer.put(key.char)
                    key.time_pressed = scan_time
                elif key.state == 1 and node_state == 0:
                    key.state = 0
            await asyncio.sleep_ms(200)


class Key:
    """ keypad key-switch
        - key-press time saved as ticks_ms for future dev
    """

    def __init__(self, char):
        self._char = char
        self.state = 0
        self.pressed = False
        self.time_pressed = None

    @property
    def char(self):
        return self._char

    def __str__(self):
        return self.char


async def get_char(buffer_):
    """ get char type from character sets """
    digits = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9'}
    letters = {'A', 'B', 'C', 'D'}
    symbols = {'*', '#'}
    
    char_ = await buffer_.get()
    if char_ in digits:
        char_type_ = 'digit'
    elif char_ in letters:
        char_type_ = 'letter'
    elif char_ in symbols:
        char_type_ = 'symbol'
    else:
        char_type_ = None
    return char_type_, char_


async def lexer(buffer):
    """ consumer: demonstrate buffered input
        - very basic lexer included
    """

    # tokens = {'integer', 'string', 'symbol'}
    
    token_type = None
    token_value = None
    while True:
        char_type, char = await get_char(buffer)
        if char_type == 'digit':
            token_type = 'integer'
            token_value = char
            while True:
                print(f'Entered: {token_value}')
                char_type, char = await get_char(buffer)
                if char_type == 'digit':
                    token_value += char
                elif char_type == 'symbol':
                    if char == '#':
                        break
                else:
                    print('Enter digit or #')
        elif char_type == 'letter':
            token_type = 'string'
            token_value = char
            while True:
                print(f'Entered: {token_value}')
                char_type, char = await get_char(buffer)
                if char_type == 'letter' or char_type == 'digit':
                    token_value += char
                elif char_type == 'symbol':
                    if char == '#':
                        break
                else:
                    print('Enter letter, digit or #')
        elif char_type == 'symbol':
            token_type = 'symbol'
            token_value = char

        if token_type == 'integer':
            token_value = int(token_value)
        print(f'token: {token_type} value: {token_value}')


async def main():
    # KeyPad: RPi Pico pin assignments
    cols = (12, 13, 14, 15)
    rows = (8, 9, 10, 11)

    buffer = KeyBuffer()
    kp = KeyPad(cols, rows, buffer)
    print('Press # to end integer or string input.')
    asyncio.create_task(lexer(buffer))
    await kp.key_input()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
