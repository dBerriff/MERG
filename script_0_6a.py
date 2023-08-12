""" Read matrix keypad with Pi Pico """

from machine import Pin
import uasyncio as asyncio


class KeyBuffer:
    """ single item buffer
        - similar interface to Queue
        - Event.set() "must be called from within a task"
        - hence add() and pop() are coros
        - put_lock added for consistency with queue:
            supports multiple data producers
    """
    
    def __init__(self):
        self._item = None
        self.is_data = asyncio.Event()
        self.is_space = asyncio.Event()
        self.put_lock = asyncio.Lock()
        self.is_space.set()
    
    async def put(self, item):
        """ add item to buffer
            - demonstrates use of async Lock()
        """
        async with self.put_lock:
            # only one task can acquire the lock at any one time
            await self.is_space.wait()
            self._item = item
            self.is_data.set()
            self.is_space.clear()

    async def get(self):
        """ remove item from buffer """
        await self.is_data.wait()
        self.is_space.set()
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
    # hex values relate directly to column and row numbers
    key_values = {0x00: '1', 0x01: '2', 0x02: '3', 0x03: 'A',
                  0x10: '4', 0x11: '5', 0x12: '6', 0x13: 'B',
                  0x20: '7', 0x21: '8', 0x22: '9', 0x23: 'C',
                  0x30: '*', 0x31: '0', 0x32: '#', 0x33: 'D'
                  }

    def __init__(self, cols, rows, buffer):
        super().__init__(cols, rows)
        self.buffer = buffer

    async def key_input(self):
        """ coro: detect single key-press in switch matrix
                - data producer (put into buffer)
        """
        new_press = True
        # poll switches
        while True:
            node = self.scan_switch()
            if node is None:
                new_press = True  # previous key released
            elif new_press:
                key_ = self.key_values[node]
                await self.buffer.put(key_)
                new_press = False  # supress repeat readings
            await asyncio.sleep_ms(20)


async def print_buffer(buffer):
    """ consumer: demonstrate buffered input """
    print('Waiting for keypad input...')
    prev_char = ''
    while True:
        char = await buffer.get()
        print(char)
        if char == '*' and prev_char == '*':
            break
        prev_char = char
    print('break from print_buffer')


async def main():
    # KeyPad: RPi Pico pin assignments
    cols = (8, 9, 10, 11)
    rows = (12, 13, 14, 15)

    buffer = KeyBuffer()
    kp = KeyPad(cols, rows, buffer)
    asyncio.create_task(kp.key_input())
    await print_buffer(buffer)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
