""" basic lexer
    - for asyncio guidance and source acknowledged, see:
      https://github.com/peterhinch/micropython-async
"""

import uasyncio as asyncio
from micropython import const


class LToken:
    """ lexer/parser token """
    
    INT = const('int')
    STR = const('str')
    SMB = const('smb')
    
    val_type = {'int': int, 'smb': str, 'str': str}

    def __init__(self):
        self.type = None
        self.value = None

    def set_type(self):
        """ set token value to type int """
        if self.type in self.val_type:
            self.value = self.val_type[self.type](self.value)
        else:
            self.type = None

    def __str__(self):
        return f'{self.type} {self.value} {type(self.value)}'
        

class Lexer:
    """ 'Tokenize' input stream using an simple lexer.
        Parameters:
        - kp_: object, includes keypad characters
        - get_char_: method
    """

    def __init__(self, kp_, get_char_):
        self.get_char = get_char_
        self.digits = kp_.digits
        self.letters = kp_.letters
        self.alphanumeric = kp_.alphanumeric
        self.symbols = kp_.symbols

    async def get_token(self):
        """ extremely basic lexer
            - tokenize integers, strings and symbols
            - integer starts with a digit
            - string starts with a letter
            - symbol is a single character
        """

        async def scan_input(string_, char_set):
            """ serial input scanner, returns input as string
                - '*': delete char
                - '#': end scan
            """
            while True:
                print(f'Entered: {string_}')
                char_ = await self.get_char()
                if char_ in char_set:
                    string_ += char_
                elif char_ == '*':
                    if len(string_) > 1:
                        string_ = string_[:-1]
                    else:
                        return None
                elif char_ == '#':
                    return string_

        token_ = LToken()
        char = await self.get_char()
        if char in self.digits:
            token_.type = token_.INT
            token_.value = await scan_input(char, self.digits)
        elif char in self.letters:
            token_.type = token_.STR
            token_.value = await scan_input(char, self.alphanumeric)
        elif char in self.symbols:
            token_.type = token_.SMB
            token_.value = char
        if not token_.value:
            token_.type = None
        return token_


async def main():
    """ Test by calling from keypad.py """
    print('In main()')
    print('Test by calling from keypad.py')
    

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
