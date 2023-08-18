"""
    Read matrix keypad with Pi Pico
    Generic keypad supplied as component in Elegoo kit.
    Simple "membrane" switches close at each column-to-row intersection
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

    queue.py and parser.py must be uploaded to the Pi Pico
"""

from machine import Pin
import uasyncio as asyncio
from time import ticks_ms
from queue import CharBuffer
from parser import Lexer


class SwitchMatrix:
    """ matrix of switched nodes
        - matrix data returned as linear list index: index = (row * n_cols + col)
        - m_list as list; array gives marginal or no greater efficiency
    """
    
    def __init__(self, cols, rows):
        # columns are scanned inputs; rows are outputs set high in sequence
        self.col_pins = [Pin(pin, mode=Pin.IN, pull=Pin.PULL_DOWN) for pin in cols]
        self.row_pins = [Pin(pin, mode=Pin.OUT, value=0) for pin in rows]
        self._list_len = len(cols) * len(rows)
        self.m_list = [0] * len(self)  # fixed-length list

    def __len__(self):
        return self._list_len

    def scan_matrix(self):
        """ scan matrix nodes """
        index = 0
        for r_pin in self.row_pins:
            r_pin.high()
            for c_pin in self.col_pins:
                self.m_list[index] = c_pin.value()
                index += 1
            r_pin.low()
        return self.m_list


class KeyPad(SwitchMatrix):
    """ process SwitchMatrix as matrix of Key objects
        - output key-value to Buffer object
        - matrix nodes and key objects matched in (col, row) order
    """
    key_char_list = (
        '1', '2', '3', 'A',
        '4', '5', '6', 'B',
        '7', '8', '9', 'C',
        '*', '0', '#', 'D'
    )

    digits = '0123456789'
    letters = 'ABCD'
    symbols = '*#'

    def __init__(self, cols, rows, buffer):
        super().__init__(cols, rows)
        self.buffer = buffer
        self.key_list = []
        for char in KeyPad.key_char_list:
            key = Key(char)
            self.key_list.append(key)
 
    async def key_input(self):
        """ coro: detect key-press in switch matrix
            - data producer: put char into buffer
            - detects multiple presses
        """
        # scan matrix repeatedly
        while True:
            scan_time = ticks_ms()
            matrix_states = self.scan_matrix()
            for index in range(len(self)):
                node_state = matrix_states[index]
                key = self.key_list[index]
                if node_state == 1 and key.state == 0:
                    key.state = 1  # key has been pressed
                    key.time_pressed = scan_time
                    await self.buffer.put(key.char)
                elif node_state == 0 and key.state == 1:
                    key.state = 0  # key has been released
            await asyncio.sleep_ms(200)  # scan interval


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
        return self._char


async def main():
    """ test keypad input and parsing """
    
    async def consumer(lex_):
        """ consume input characters """
        while True:
            print('Integer: enter a digit; String: enter a letter:')
            t_type, t_value = await lex_.get_token()
            print(f'token: {t_type} value: {t_value}')

    # KeyPad: RPi Pico pin assignments
    cols = (12, 13, 14, 15)
    rows = (8, 9, 10, 11)

    buffer = CharBuffer()
    kp = KeyPad(cols, rows, buffer)
    lex = Lexer(kp, buffer)
    prompt = '- Integers start with a number, strings with a letter\n'
    prompt += '- Press # to end integer or string input, * to delete a character\n'
    print(prompt)
    asyncio.create_task(consumer(lex))
    await kp.key_input()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
