""" basic lexer """

import uasyncio as asyncio


class Lexer:
    """ implemented as class for consistent script structure but
        could also be implemented as a function.
        'Tokenize' input stream using an extremely simple lexer.
        Parameters:
        - kp_: for keypad characters;
        - get_char_: get next character
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
            - an integer starts with a digit
            - a string starts with a letter
            - a symbols is a single character
        """

        async def scan_input(token_value_, char_set):
            """ serial input scanner
                - a symbol or full delete ends scan
                - '#' ends input with current value
                - '*' deletes latest char
            """
            while True:
                print(f'Entered: {token_value_}')
                char_ = await self.get_char()
                if char_ in char_set:
                    token_value_ += char_
                elif char_ == '*':
                    if len(token_value_) > 1:
                        token_value_ = token_value_[:-1]
                    else:
                        token_value_ = None
                        break
                elif char_ == '#':
                    break
            return token_value_

        token_type = None
        token_value = None
        char = await self.get_char()
        if char in self.digits:
            token_value = await scan_input(char, self.digits)
            if token_value:
                token_value = int(token_value)
                token_type = 'integer'
        elif char in self.letters:
            token_value = await scan_input(char, self.alphanumeric)
            if token_value:
                token_type = 'string'
        elif char in self.symbols:
            token_value = char
            token_type = 'symbol'
        return token_type, token_value


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
