"""
    Read matrix keypad with Pi Pico
    Hardware: generic 4-column, 4-row keypad
    Simple "membrane" switches close at each column-to-row intersection
    =======
    1 2 3 A
    4 5 6 B
    7 8 9 C
    * 0 # D
    =======

    8 x connectors, left-to-right, from Elegoo diagram:
    
    0:  1-2-3-A  Rows
    1:  4-5-6-B
    2:  7-8-9-C
    3:  *-0-#-D
    4:  1-4-7-*  Cols
    5:  2-5-8-0
    6:  3-6-9-#
    7:  A-B-C-D

    In code, coordinate order is (col, row)
"""
# queue.py and parser.py must be uploaded to the Pico
from machine import Pin
import uasyncio as asyncio
from queue import CharBuffer
from parser import Lexer, LToken


class SwitchMatrix:
    """ matrix of switched nodes
        - matrix data returned as linear list: index = (row * n_cols + col)
    """
    
    def __init__(self, cols, rows):
        # rows set high in sequence, columns scanned as inputs
        self.col_pins = [Pin(pin, mode=Pin.IN, pull=Pin.PULL_DOWN) for pin in cols]
        self.row_pins = [Pin(pin, mode=Pin.OUT, value=0) for pin in rows]
        self._list_len = len(cols) * len(rows)
        self.m_list = [0] * self._list_len  # fixed-length list

    def __len__(self):
        """ length of matrix as list """
        return self._list_len

    def scan_matrix(self):
        """ scan matrix nodes by (col, row) """
        index = 0
        for r_pin in self.row_pins:
            r_pin.high()
            for c_pin in self.col_pins:
                self.m_list[index] = c_pin.value()
                index += 1  # row * n_cols + col
            r_pin.low()
        return self.m_list


class KeyPad(SwitchMatrix):
    """ process SwitchMatrix as tuple of Key objects
        - output key-value to Buffer object
        - matrix nodes and key objects matched in (col, row) order
    """
    key_char_list = tuple('123A456B789C*0#D')  # iterable
    digits = set('0123456789')
    letters = set('ABCD')
    symbols = set('*#')
    alphanumeric = digits.union(letters)

    def __init__(self, cols, rows, buffer):
        super().__init__(cols, rows)
        self.buffer = buffer
        self.key_list = tuple([Key(char) for char in KeyPad.key_char_list])
 
    async def key_input(self):
        """ coro: detect key-presses in switch matrix
            - data producer: put char into buffer
        """
        scan_interval = 100  # ms - adjust as required
        while True:
            m_states = self.scan_matrix()
            for index in range(len(self)):
                node_state = m_states[index]
                key = self.key_list[index]
                if key.state != node_state:
                    if node_state == 1:
                        await self.buffer.put(key.char)
                    key.state = node_state
            await asyncio.sleep_ms(scan_interval)


class Key:
    """ keypad key-switch """

    def __init__(self, char):
        self._char = char
        self.state = 0
        self.pressed = False

    @property
    def char(self):
        return self._char

    def __str__(self):
        return self._char


async def main():
    """ test keypad input and parsing """

    async def consumer(lex_):
        """ consume input characters """
        # tokens returned as t_type: 'integer', 'string' or 'symbol'
        t_ = LToken()
        print('consumer() started: enter "DDD" to end')
        while t_.value != 'DDD':
            print('Integer: enter a digit; String: enter a letter:')
            t_ = await lex_.get_token()
            t_.set_type()
            print(t_)

    # KeyPad: RPi Pico pin assignments
    cols = (12, 13, 14, 15)
    rows = (8, 9, 10, 11)

    buffer = CharBuffer()
    kp = KeyPad(cols, rows, buffer)
    lex = Lexer(kp, buffer.get)
    prompt = '- Integers start with a number, strings with a letter\n'
    prompt += '- Press # to end integer or string input, * to delete a character\n'
    print(prompt)
    asyncio.create_task(kp.key_input())
    await consumer(lex)
    print('Test complete')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
