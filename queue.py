""" Queue class """

import uasyncio as asyncio


class Queue:
    """ FIFO queue
        - is_data and is_space events control access
        - Event.set() "must be called from within a task",
          hence coros.
        - using array rather than list gave no measurable advantages
        - a larger queue length runs more slowly in this test
            but might be required for specific input buffering
    """

    def __init__(self, length):
        self.length = length
        self.queue = [None] * length
        self.head = 0
        self.next = 0
        self.is_data = asyncio.Event()
        self.is_space = asyncio.Event()
        self.put_lock = asyncio.Lock()
        self.is_space.set()

    async def put(self, item):
        """ add item to the queue
            - Lock required if multiple put tasks
        """
        async with self.put_lock:
            await self.is_space.wait()
            self.queue[self.next] = item
            self.next = (self.next + 1) % self.length
            if self.next == self.head:
                self.is_space.clear()
            self.is_data.set()

    async def get(self):
        """ remove item from the queue
            - single consumer assumed
        """
        await self.is_data.wait()
        item = self.queue[self.head]
        self.head = (self.head + 1) % self.length
        if self.head == self.next:
            self.is_data.clear()
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


class CharBuffer:
    """ single item buffer
        - similar interface to Queue
        - put_lock supports multiple data producers
    """
    
    def __init__(self):
        self._item = None
        self.is_data = asyncio.Event()
        self.is_space = asyncio.Event()
        self.put_lock = asyncio.Lock()
        self.is_space.set()
    
    async def put(self, item):
        """ add item to buffer
            - Lock() allows multiple producers
        """
        async with self.put_lock:
            await self.is_space.wait()
            self._item = item
            self.is_data.set()
            self.is_space.clear()

    async def get(self):
        """ remove item from buffer
            - assumes single consumer
        """
        await self.is_data.wait()
        self.is_space.set()
        self.is_data.clear()
        return self._item


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
        return p_list

    # test KeyBuffer or Queue with 2 producers
    queue = CharBuffer()
    # queue = Queue(8)

    task0 = asyncio.create_task(fill_q(queue, 0, 20))
    task1 = asyncio.create_task(fill_q(queue, 50, 100))
    q_data = await asyncio.create_task(empty_q(queue))
    print('unsorted gets')
    print(q_data)
    q_data.sort()
    print('sorted gets')
    print(q_data)

    task0.cancel()
    task1.cancel()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
