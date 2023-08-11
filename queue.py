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

    async def put(self, item):
        """ add item to the queue """
        next_ = self.next
        self.queue[next_] = item
        next_ = (next_ + 1) % self.max_len
        if next_ == self.head:
            self.is_space.clear()
        self.next = next_
        self.is_data.set()

    async def get(self):
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
            n = self.max_len if self.is_data.is_set() else 0
        else:
            n = (self.next - self.head) % self.max_len
        return n

    def q_print(self):
        """ print out all queue-item values """
        print(f'head: {self.head}; next: {self.next}; length: {self.q_len}')
        q_str = '['
        for i in range(self.max_len):
            q_str += f'{self.queue[i]}, '
        q_str = q_str[:-2] + ']'
        print(q_str)


async def main():
    """ test Queue class """
    print('In main()')
    
    async def fill_q(q_, n):
        """ fill queue with test integers """
        for i in range(n):
            await queue.is_space.wait()
            await queue.put(i)
        
    async def empty_q(q_):
        """ empty and print queue elements """
        while queue.is_data.is_set():
            p = await queue.get()
            print(p, q_.q_len)
            await asyncio.sleep_ms(0)

    queue = Queue('B')
    queue.q_print()
    asyncio.create_task(fill_q(queue, 32))
    await asyncio.sleep_ms(0)  # let scheduler run tasks
    queue.q_print()
    # empty the queue
    await empty_q(queue)
    queue.q_print()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
