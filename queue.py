""" Queue class """

import uasyncio as asyncio
import array


class QueueBase:
    """ abstract base class for FIFO queue
        - is_data and is_space events control access
        - Event.set() "must be called from within a task",
          hence coros.
    """

    def __init__(self, length):
        self.length = length
        self.queue = None
        self.head = 0
        self.next = 0
        self.is_data = asyncio.Event()
        self.is_space = asyncio.Event()
        self.put_lock = asyncio.Lock()
        self.get_lock = asyncio.Lock()
        self.is_space.set()

    async def put(self, item):
        """ add item to the queue
            - Lock required if multiple put tasks
        """
        async with self.put_lock:
            await self.is_space.wait()
            next_ = self.next
            self.queue[next_] = item
            next_ = (next_ + 1) % self.length
            if next_ == self.head:
                self.is_space.clear()
            self.next = next_
            self.is_data.set()

    async def get(self):
        """ remove item from the queue
            - Lock required if multiple get tasks
        """
        async with self.get_lock:
            await self.is_data.wait()
            head_ = self.head
            item = self.queue[head_]
            head_ = (head_ + 1) % self.length
            if head_ == self.next:
                self.is_data.clear()
            self.head = head_
            self.is_space.set()
            return item

    @property
    def q_len(self):
        """ number of items in the queue """
        if self.head == self.next:
            n = self.length if self.is_data.is_set() else 0
        else:
            n = (self.next - self.head) % self.length
        return n

    def q_print(self):
        """ print out queue values """
        print(f'head: {self.head}; next: {self.next}; length: {self.q_len}')
        q_str = '['
        for i in range(self.length):
            q_str += f'{self.queue[i]}, '
        q_str = q_str[:-2] + ']'
        print(q_str)


class QueueArray(QueueBase):
    """ queue as array of specified object type
        - more efficient than a list of objects but limited types
        - selected type-codes for unsigned int values:
            'B' 1-byte; 'I' 2-byte; 'L' 4-byte
    """

    def __init__(self, length, type_code):
        super().__init__(length)
        self.queue = array.array(type_code, [0] * length)


class QueueList(QueueBase):
    """ queue as list of objects """
    def __init__(self, length):
        super().__init__(length)
        self.queue = [None] * length


async def main():
    """ test Queue class """
    print('In main()')

    async def fill_q(q_, n, m):
        """ fill queue with test integers """
        for i in range(n, m):
            await q_.put(i)
        
    async def empty_q(q_):
        """ empty and print queue elements """
        p_list = []
        while q_.is_data.is_set():
            p = await q_.get()
            p_list.append(p)
            await asyncio.sleep_ms(1)  # let fill_q() get run
        print('unsorted gets')
        print(p_list)
        p_list.sort()
        print('sorted gets')
        print(p_list)

    queue = QueueArray(8, 'B')
    task0 = asyncio.create_task(fill_q(queue, 0, 20))
    task1 = asyncio.create_task(fill_q(queue, 50, 100))
    await asyncio.create_task(empty_q(queue))
    task0.cancel()
    task1.cancel()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
