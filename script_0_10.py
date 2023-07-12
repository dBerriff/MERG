""" develop button input """
import uasyncio as asyncio
from machine import Pin
from time import ticks_ms, ticks_diff


class Button:
    """ button with press and hold states """
    
    # class variable: unique object id
    _id = 0
    
    action_dict = {0: 'none', 1: 'press', 2: 'hold'}
    hold_t = 750  # ms

    def __init__(self, pin, out_queue):
        self._hw_in = Pin(pin, Pin.IN, Pin.PULL_UP)
        self.out_queue = out_queue
        self.id = Button._id  # identify event source
        Button._id += 1
        self.button_ev = asyncio.Event()

    async def poll_input(self):
        """ poll button for press or hold events """
        on_time = 0
        prev_state = 1  # button off; pull-up logic
        while True:
            state = self._hw_in.value()
            if state != prev_state:
                time_stamp = ticks_ms()
                if state == 1:
                    if ticks_diff(time_stamp, on_time) < Button.hold_t:
                        action = 1
                    else:
                        action = 2
                    await self.out_queue.add((self.id, action))
                    self.button_ev.set()
                else:
                    on_time = time_stamp
                prev_state = state
            await asyncio.sleep_ms(20)


class QueueKV:
    """ simple FIFO lists as queue of keys and values
        - is_data and is_space events control access
        - Event.set() "must be called from within a task",
            hence coros.
    """

    def __init__(self, max_len=16, null_item=0):
        self.max_len = max_len
        self.queue = [null_item] * max_len
        self.head = 0
        self.next = 0
        self.is_data = asyncio.Event()
        self.is_space = asyncio.Event()
        self.is_space.set()

    async def add(self, item):
        """ add item to the queue """
        next_ = self.next
        self.queue[next_] = item
        self.next = (next_ + 1) % self.max_len
        if self.next == self.head:
            self.is_space.clear()
        self.is_data.set()

    async def pop(self):
        """ remove item from the queue """
        head_ = self.head
        item = self.queue[head_]
        self.head = (head_ + 1) % self.max_len
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

    def q_dump(self):
        """ print of all queue items """
        for i in range(self.max_len):
            print(self.queue[i])


async def button_event(q_in):
    """ respond to queued button events """
    run = True
    while run:
        await q_in.is_data.wait()
        item = await q_in.pop()
        key, value = item
        print(f'button: {key} value: {value}')
        if item == (2, 2):
            run = False


async def main():
    """ test button input """
    print('In main()')
    queue = QueueKV(null_item=(0, 0))
    btn_group = tuple([Button(pin, queue) for pin in [20, 21, 22]])
    print(btn_group)
    for button in btn_group:    
        asyncio.create_task(button.poll_input())
    await button_event(queue)
    queue.q_dump()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
