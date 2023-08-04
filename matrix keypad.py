""" Read matrix keypad with Pi Pico """

from machine import Pin
import uasyncio as asyncio


class KeyBuffer:
    """ single item buffer
        - similar interface to Queue
        - Event.set() "must be called from within a task"
        - hence add() and pop() as coros
    """
    
    def __init__(self):
        self.item = None
        self.is_data = asyncio.Event()
    
    async def add(self, item):
        """ add item to buffer """
        self.item = item
        self.is_data.set()

    async def pop(self):
        """ remove item from buffer """
        self.is_data.clear()
        return self.item


class SwitchMatrix:
    """ scan matrix with up to 16 x 16 switched nodes """
    
    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        # Set col pins as outputs, row pins as inputs
        self.col_pins = tuple(
            [Pin(pin, mode=Pin.OUT) for pin in cols])
        self.row_pins = tuple(
            [Pin(pin, mode=Pin.IN, pull=Pin.PULL_DOWN) for pin in rows])
        for pin in self.col_pins:
            pin.low()

    def scan(self):
        """ scan for closed matrix switch """
        for col, c_pin in enumerate(self.col_pins):
            c_pin.high()
            for row, r_pin in enumerate(self.row_pins):
                if r_pin.value():
                    c_pin.low()
                    return (col << 4) + row
            c_pin.low()
        return None


class KeyPad(SwitchMatrix):
    """ process keypad input
        - producer: demonstrate buffered output """
    key_values = {0: '1', 1: '2', 2: '3', 3: 'A',
                  16: '4', 17: '5', 18: '6', 19: 'B',
                  32: '7', 33: '8', 34: '9', 35: 'C',
                  48: '*', 49: '0', 50: '#', 51: 'D'}

    def __init__(self, cols, rows, buffer):
        super().__init__(cols, rows)
        self.buffer = buffer

    async def key_input(self):
        """ accept single key-press but skip any repeated returns """
        new_press = True  # ready for first key press
        while True:
            node = self.scan()
            if node is None:
                new_press = True  # previous key has been released
            elif new_press:
                # save key value in buffer
                await self.buffer.add(self.key_values[node])
                new_press = False  # reject repeat readings
            await asyncio.sleep_ms(100)


async def print_buffer(buffer):
    """ consumer: demonstrate buffered input """
    while True:
        # is_data set when an item is added to buffer
        await buffer.is_data.wait()
        char = await buffer.pop()
        print(char)
    

async def main():
    # RPi Pico pin assignments
    cols = (8, 9, 10, 11)
    rows = (12, 13, 14, 15)

    buff = KeyBuffer()
    kp = KeyPad(cols, rows, buff)
    asyncio.create_task(print_buffer(buff))
    await kp.key_input()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
