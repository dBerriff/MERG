"""
    Read matrix keypad with Pi Pico
    Generic keypad supplied as component in Elegoo kit.
    Simple "membrane" switches close at each column-to-row intersection
        1-2-3-A
        4-5-6-B
        7-8-9-C
        *-0-#-D
    Connections numbered from left-to-right;
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
        - rationale: simple, quick code hidden from end-user
        - switch each matrix row ON and scan each column for input
        - m_list as list; array gives marginal benefits, if any
    """
    
    def __init__(self, cols, rows):
        # columns are scanned inputs; rows are outputs set high in sequence
        self.col_pins = [Pin(pin, mode=Pin.IN, pull=Pin.PULL_DOWN) for pin in cols]
        self.row_pins = [Pin(pin, mode=Pin.OUT, value=0) for pin in rows]
        # matrix scanned into list with (col, row) coordinates
        self.n_cols = len(cols)
        self.n_rows = len(rows)
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

    digits = '0123456789'
    letters = 'ABCD'
    symbols = '*#'

    def __init__(self, cols, rows, buffer):
        super().__init__(cols, rows)
        self.buffer = buffer
        # maintain correspondence between m_list and key_list
        self.key_list = []
        # dict for future processing
        self.char_key = {}
        for char in self.key_char_list:
            key = Key(char)
            self.key_list.append(key)
            self.char_key[char] = key

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
                    key.time_pressed = scan_time
                    await self.buffer.put(key.char)
                elif node_state == 0 and key.state == 1:
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


class Lexer:
    """ implemented as class for consistent script structure but
        could also be implemented as a function.
        'Tokenize' input stream using an extremely simple lexer.
    """

    def __init__(self, kp_, buffer_):
        self.kp = kp_
        self.buffer = buffer_
        self.digits = kp_.digits
        self.letters = kp_.letters
        self.symbols = kp_.symbols

    async def get_char(self):
        """ get char from buffer
            - type matched to keypad character set
        """
        char_ = await self.buffer.get()
        if char_ in self.digits:
            char_type_ = 'digit'
        elif char_ in self.letters:
            char_type_ = 'letter'
        elif char_ in self.symbols:
            char_type_ = 'symbol'
        else:
            char_type_ = None
        return char_type_, char_

    async def get_token(self):
        """ extremely basic lexer
            - tokenize integers, strings and symbols
            - tokens are: 'integer', 'string' or 'symbol'}
        """

        async def scan_stream(token_type_, token_value_, char_set):
            """ simple serial scanner to string; symbols end scan:
                - '#' ends input with current value
                - '*' deletes last char; if value becomes empty, returns None
            """
            while True:
                print(f'Entered: {token_value_}')
                char_type_, char_ = await self.get_char()
                if char_type_ in char_set:
                    token_value_ += char_
                elif char_type_ == 'symbol':
                    if char_ == '*':
                        if len(token_value_) > 1:
                            token_value_ = token_value_[:-1]
                        else:
                            token_type_ = None
                            token_value_ = None
                            break
                    elif char_ == '#':
                        break
                else:
                    print('Enter a digit or #')
            return token_type_, token_value_

        token_type = None
        token_value = None
        char_type, char = await self.get_char()

        if char_type == 'digit':
            token_type = 'integer'
            token_value = char
            token_type, token_value = await scan_stream(
                token_type, token_value, {'digit'})
        elif char_type == 'letter':
            token_type = 'string'
            token_value = char
            token_type, token_value = await scan_stream(
                token_type, token_value, {'letter', 'digit'})
        elif char_type == 'symbol':
            token_type = 'symbol'
            token_value = char

        if token_type == 'integer':
            token_value = int(token_value)
        return token_type, token_value


async def main():
    """ test keypad input and parsing """
    
    async def consumer(lex_):
        """ consume input stream """
        while True:
            print('Integer: enter a digit; String: enter a letter:')
            t_type, t_value = await lex_.get_token()
            print(f'token: {t_type} value: {t_value}')

    # KeyPad: RPi Pico pin assignments
    cols = (12, 13, 14, 15)
    rows = (8, 9, 10, 11)

    buffer = KeyBuffer()
    kp = KeyPad(cols, rows, buffer)
    lex = Lexer(kp, buffer)
    prompt = """    - Integers start with a number, strings with a letter
    - Press # to end integer or string input, * to delete a character"""
    print(prompt)
    print()
    asyncio.create_task(consumer(lex))
    await kp.key_input()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
