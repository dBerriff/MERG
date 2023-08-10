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
from queue import Queue
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
                    await self.out_queue.put(self.id)
                    await self.out_queue.is_space.wait()  # space in queue?
                    await self.out_queue.put(event)
                else:
                    on_time = time_stamp
                prev_state = state
            await asyncio.sleep_ms(20)


async def button_event(q_in):
    """ respond to queued button events """
    run = True
    while run:
        await q_in.is_data.wait()
        btn_id = await q_in.get()
        await q_in.is_data.wait()
        btn_event = await q_in.get()
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
