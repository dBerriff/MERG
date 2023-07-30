""" asyncio button input
    - poll buttons and add button press or hold action to a queue
    - identify buttons by unique ID rather than pin
    - button_ev Event is set when data is added to the queue
    - events are set on button release
    - Queue uses the array class for efficiency
"""
import uasyncio as asyncio
from machine import Pin
from time import ticks_ms, ticks_diff
from script_0_10 import Queue


def encode_id_data(id_, data):
    """ encode id and event as single byte
        - event: 0: none; 1: click; 2: hold
    """
    return (id_ << 2) + data


def decode_id_data(info_byte):
    """ return id, event """
    return info_byte >> 2, info_byte & 0b11


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
            - encoded event includes id as most significant bits
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
                    await self.out_queue.add(encode_id_data(self.id, event))
                else:
                    on_time = time_stamp
                prev_state = state
            await asyncio.sleep_ms(20)


async def button_event(q_in):
    """ respond to queued button events """
    run = True
    while run:
        await q_in.is_data.wait()
        btn_data = await q_in.pop()
        btn_id, btn_event = decode_id_data(btn_data)
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
