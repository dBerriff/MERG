""" Read matrix keypad with Pi Pico """

from machine import Pin
import uasyncio as asyncio


class KeyBuffer:
    """ single item buffer
        - similar interface to Queue
        - Event.set() "must be called from within a task"
        - hence add() and pop() are coros
    """
    
    def __init__(self):
        self._item = None
        self.is_data = asyncio.Event()
    
    async def add(self, item):
        """ add item to buffer """
        self._item = item
        self.is_data.set()

    async def pop(self):
        """ remove item from buffer """
        self.is_data.clear()
        return self._item


class SwitchMatrix:
    """ matrix of up to 16 x 16 switched nodes """
    
    def __init__(self, cols, rows):
        self.cols = cols  # outputs
        self.rows = rows  # inputs
        self.col_pins = tuple(
            [Pin(pin, mode=Pin.OUT) for pin in cols])
        self.row_pins = tuple(
            [Pin(pin, mode=Pin.IN, pull=Pin.PULL_DOWN) for pin in rows])
        for pin in self.col_pins:
            pin.low()  # all columns off

    def scan_switch(self):
        """ scan for first closed matrix-switch
            - return encoded byte of col,row; 4 bits each
        """
        for col, c_pin in enumerate(self.col_pins):
            c_pin.high()
            for row, r_pin in enumerate(self.row_pins):
                if r_pin.value():
                    c_pin.low()
                    return (col << 4) + row
            c_pin.low()
        # no key-press detected
        return None


class KeyPad(SwitchMatrix):
    """ process matrix keypad input
        - output key-value to Buffer object
    """
    key_values = {0: '1', 1: '2', 2: '3', 3: 'A',
                  16: '4', 17: '5', 18: '6', 19: 'B',
                  32: '7', 33: '8', 34: '9', 35: 'C',
                  48: '*', 49: '0', 50: '#', 51: 'D'}

    def __init__(self, cols, rows, buffer):
        super().__init__(cols, rows)
        self.buffer = buffer

    async def key_input(self):
        """ detect single key-press in switch matrix """
        key_ = None
        new_press = True
        # poll switches
        while True:
            node = self.scan_switch()
            if node is None:
                new_press = True  # previous key released
            elif new_press:
                key_ = self.key_values[node]
                if key_ == '*':
                    break  # end while loop
                await self.buffer.add(key_)
                new_press = False  # supress repeat readings
            await asyncio.sleep_ms(20)


async def print_buffer(buffer):
    """ consumer: demonstrate buffered input """
    print('Waiting for keypad input...')
    while True:
        # is_data set when an item is added to buffer
        await buffer.is_data.wait()
        char = await buffer.pop()
        print(char)


async def main():
    # RPi Pico pin assignments
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
