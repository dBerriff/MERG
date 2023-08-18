""" Very basic lexer """

import uasyncio as asyncio


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
            """ serial scanner to string; symbols end scan:
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
            return token_type_, token_value_

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
        else:
            token_type = None
            token_value = None

        if token_type == 'integer':
            token_value = int(token_value)
        return token_type, token_value


async def main():
    """ test keypad input and parsing """
    print('In main()')
    

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
