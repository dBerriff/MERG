""" asyncio button input
    - poll buttons and add button press or hold action to a queue
    - encode id and event as single value
    - button_ev Event is set when data is added to the queue
    - events are set on button release
    - Queue uses the array class for efficiency
"""
import uasyncio as asyncio
from machine import Pin
from micropython import const
from time import ticks_ms, ticks_diff
from queue import Queue


class Button:
    """ button with press and hold states """
    
    # class variable: unique object id
    _id = 0
    
    off = const(1)
    on = const(0)
    click = const(1)
    hold = const(2)

    hold_min = const(750)  # ms

    def __init__(self, pin, q_out):
        self._hw_in = Pin(pin, Pin.IN, Pin.PULL_UP)
        self.q_out = q_out
        self.id_ = Button._id  # identify event source
        Button._id += 1
        self.button_ev = asyncio.Event()

    async def poll_input(self):
        """ poll button for press or hold events
            - encoded event includes id as most significant bits
            - add each event to out_queue
        """
        on_time = 0
        prev_state = Button.off
        while True:
            state = self._hw_in.value()
            if state != prev_state:
                time_stamp = ticks_ms()
                if state == Button.off:
                    hold_t = ticks_diff(time_stamp, on_time)
                    event = 1 if hold_t < Button.hold_min else 2
                    await self.q_out.is_space.wait()  # space in queue?
                    await self.q_out.put((self.id_ << 2) + event)
                else:
                    on_time = time_stamp
                prev_state = state
            await asyncio.sleep_ms(20)


async def button_event(q_btn_event):
    """ respond to queued button events """
    run = True
    while run:
        await q_btn_event.is_data.wait()
        btn_data = await q_btn_event.get()
        btn_id = btn_data >> 2
        btn_event = btn_data & 0b11
        print(f'button: {btn_id} value: {btn_event}')
        if btn_id == 2 and btn_event == 2:
            run = False
        

async def main():
    """ test button input """
    print('In main()')
    queue = Queue('B')
    btn_group = tuple(
        [Button(pin, queue) for pin in [20, 21, 22]])
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
