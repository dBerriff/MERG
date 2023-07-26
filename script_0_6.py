"""
    Template for asyncio scripts.
    See: https://github.com/peterhinch  micropython-async
    Above source gratefully acknowledged.

    - 2 coroutines are run as a test.
"""

import uasyncio as asyncio
from machine import Pin


async def blink(led, period=1100):
    """ coro: blink the onboard LED
        - earlier versions of MicroPython require
          25 rather than 'LED' if not Pico W
    """
    # flash LED every period ms approx.
    off_ms = period - 100
    while True:
        led.on()
        await asyncio.sleep_ms(100)  # allow other tasks to run
        led.off()
        await asyncio.sleep_ms(off_ms)


async def print_numbers(i_max):
    """ coro: print integers from 0 to i_max-1 """
    for i in range(i_max):
        print(i)
        await asyncio.sleep_ms(1000)


async def main():
    """ coro: test of asyncio template """
    # create_task() does not block locally
    onboard = Pin('LED', Pin.OUT, value=0)
    asyncio.create_task(blink(onboard))  # scheduled but does not block locally
    # await blocks locally but allows scheduler to run other tasks
    await print_numbers(10)
    print('print_numbers() completed')
    onboard.off()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
