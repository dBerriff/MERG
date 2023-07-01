"""
    Template for asyncio scripts.
    See: https://github.com/peterhinch  micropython-async
    Above source gratefully acknowledged.

    - 2 coroutines are run as a test.
"""

import uasyncio as asyncio
from machine import Pin


async def blink():
    """ coro: blink the onboard LED
        - earlier versions of MicroPython require
          25 rather than 'LED' if not Pico W
    """
    onboard = Pin('LED', Pin.OUT, value=0)
    # flash LED every 500ms approx.
    while True:
        onboard.on()
        await asyncio.sleep_ms(100)  # allow other tasks to run
        onboard.off()
        await asyncio.sleep_ms(400)


async def print_numbers(i_max):
    """ coro: print integers from 0 to i_max-1 """
    for i in range(i_max):
        print(i)
        await asyncio.sleep_ms(500)


# noinspection PyAsyncCall
async def main():
    """ coro: test of asyncio template """
    # create_task() does not block locally
    asyncio.create_task(blink())  # run until task or module completes
    # await does block locally until print_numbers() completes
    await print_numbers(10)
    print('print_numbers() completed')



if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
