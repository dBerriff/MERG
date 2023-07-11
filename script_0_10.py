""" develop button input """
import uasyncio as asyncio
from machine import Pin
from time import ticks_ms, ticks_diff


class Button:
    """ button with press and hold states """
    
    _id = 0
    
    action_dict = {0: 'none', 1: 'press', 2: 'hold'}
    hold_t = 750  # ms

    def __init__(self, pin, out_queue):
        self.pin = pin  # for diagnostics
        self.out_queue = out_queue
        self.id = Button._id
        Button._id += 1
        self._hw_in = Pin(pin, Pin.IN, Pin.PULL_UP)
        self.button_ev = asyncio.Event()

    async def poll_input(self):
        """ poll button for press and hold events """
        on_time = 0
        prev_state = 0
        while True:
            state = 0 if self._hw_in.value() == 1 else 1
            if state != prev_state:
                time_ = ticks_ms()
                if state == 0:
                    if ticks_diff(time_, on_time) < self.hold_t:
                        action = 1
                    else:
                        action = 2
                    self.out_queue.add_item((self.id, action))
                    self.button_ev.set()
                else:
                    on_time = time_
                prev_state = state
            await asyncio.sleep_ms(20)


class Queue:
    """ simple FIFO list as queue
        - is_data and is_space Event.is_set() controls access
        - events should be set within tasks, hence coros.
    """

    def __init__(self, max_len=16):
        self.max_len = max_len
        self.q = [None] * max_len
        self.head = 0
        self.next = 0
        self.is_data = asyncio.Event()
        self.is_space = asyncio.Event()
        self.is_space.set()

    def add_item(self, item):
        """ add item to the queue """
        self.q[self.next] = item
        self.next = (self.next + 1) % self.max_len
        if self.next == self.head:
            self.is_space.clear()
        self.is_data.set()

    def pop_item(self):
        """ remove item from the queue """
        item = self.q[self.head]
        self.head = (self.head + 1) % self.max_len
        if self.head == self.next:
            self.is_data.clear()
        self.is_space.set()
        return item

    @property
    def q_len(self):
        """ number of items in the queue """
        if self.head == self.next:
            if self.is_data.is_set():
                n = self.max_len
            else:
                n = 0
        else:
            n = (self.next - self.head) % self.max_len
        return n


async def button_event(q_in):
    """ respond to button event
        - clear event
    """
    while True:
        await q_in.is_data.wait()
        item = q_in.pop_item()
        print(f'button input: {item}')


async def main():
    """ test button input """
    print('In main()')
    queue = Queue()
    btn_group = tuple([Button(pin, queue) for pin in [20, 21, 22]])
    print(btn_group)
    for button in btn_group:    
        asyncio.create_task(button.poll_input())
    while True:
        await button_event(queue)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
