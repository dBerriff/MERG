""" Queue class """

import uasyncio as asyncio
import array


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


async def main():
    """ test button input """
    print('In main()')
    queue = Queue('B')
    await queue.add(1)
    await queue.add(2)
    await queue.add(3)
    p = await queue.pop()
    print(p)
    p = await queue.pop()
    print(p)
    queue.q_print()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
