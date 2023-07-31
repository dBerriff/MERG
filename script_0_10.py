""" asyncio button input
    - poll buttons and add button press or hold action to a queue
    - send button id and event as separate values
    - button_ev Event is set when data is added to the queue
    - events are set on button release
    - Queue uses the array class for efficiency
"""
import uasyncio as asyncio
from machine import Pin
import array
from time import ticks_ms, ticks_diff


class Button:
    """ button with press and hold states """
    
    # class variable: unique object id
    _id = 0
    
    # action_dict = {0: 'none', 1: 'click', 2: 'hold'}
    hold_t = 750  # ms

    def __init__(self, pin, out_queue):
        self._hw_in = Pin(pin, Pin.IN, Pin.PULL_UP)
        self.out_queue = out_queue
        self.id = Button._id  # identify event source
        Button._id += 1
        self.button_ev = asyncio.Event()

    async def poll_input(self):
        """ poll button for press or hold events
            - encoded event includes self.id as least significant bits
            - add each event to out_queue
        """
        on_time = 0
        prev_state = 1  # button off; pull-up logic
        while True:
            state = self._hw_in.value()
            if state != prev_state:
                time_stamp = ticks_ms()
                if state == 1:
                    hold_t = ticks_diff(time_stamp, on_time)
                    event = 1 if hold_t < Button.hold_t else 2
                    await self.out_queue.is_space.wait()  # space in queue?
                    await self.out_queue.add(self.id)
                    await self.out_queue.is_space.wait()  # space in queue?
                    await self.out_queue.add(event)
                else:
                    on_time = time_stamp
                prev_state = state
            await asyncio.sleep_ms(20)


class Queue:
    """ simple FIFO array of value: type-code
        selected type-codes for unsigned int values:
        'B' 1-byte; 'I' 2-byte; 'L' 4-byte
        - is_data and is_space events control access
        - Event.set() "must be called from within a task",
            hence coros.
    """

    def __init__(self, type_code, max_len=16):
        self.max_len = max_len
        self.queue = array.array(type_code, [0] * max_len)  # unsigned single-byte integer
        self.head = 0
        self.next = 0
        self.is_data = asyncio.Event()
        self.is_space = asyncio.Event()
        self.is_space.set()

    async def add(self, item):
        """ add item to the queue """
        next_ = self.next
        self.queue[next_] = item
        next_ = (next_ + 1) % self.max_len
        if next_ == self.head:
            self.is_space.clear()
        self.next = next_
        self.is_data.set()

    async def pop(self):
        """ remove item from the queue """
        head_ = self.head
        item = self.queue[head_]
        head_ = (head_ + 1) % self.max_len
        if head_ == self.next:
            self.is_data.clear()
        self.head = head_
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

    def q_print(self):
        """ print out all queue-item values """
        print(f'head: {self.head}; next: {self.next}')
        q_str = '['
        for i in range(self.max_len):
            q_str += f'{self.queue[i]}, '
        q_str = q_str[:-2] + ']'
        print(q_str)


async def button_event(q_in):
    """ respond to queued button events """
    run = True
    while run:
        await q_in.is_data.wait()
        btn_id = await q_in.pop()
        await q_in.is_data.wait()
        btn_event = await q_in.pop()
        print(f'button: {btn_id} value: {btn_event}')
        if btn_id == 2 and btn_event == 2:
            run = False
        

async def main():
    """ test button input """
    print('In main()')
    queue = Queue('B')
    btn_group = tuple(
        [Button(pin, queue) for pin in [20, 21, 22]])
    print(btn_group)
    for button in btn_group:    
        asyncio.create_task(button.poll_input())
    await button_event(queue)
    queue.q_print()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
