"""
    Template for asyncio scripts
    - 2 coroutines are run as a test
"""

import uasyncio as asyncio
from machine import Pin


async def blink():
    """ coro: blink the onboard LED """
    onboard = Pin('LED', Pin.OUT, value=0)
    while True:
        onboard.on()
        # allow other tasks to run
        await asyncio.sleep_ms(100)
        onboard.off()
        # allow other tasks to run
        await asyncio.sleep_ms(400)


async def print_numbers(i_max):
    """ coro: print from 0 to i_max """
    for i in range(i_max):
        print(i)
        # allow other tasks to run
        await asyncio.sleep_ms(500)


async def main():
    """ coro: test of asyncio template """
    # create_task() does not block locally
    # blink() runs until script completes
    asyncio.create_task(blink())
    # await blocks locally until coro completes
    # cooperative multitasking continues
    await print_numbers(10)
    print('print-out complete')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        asyncio.new_event_loop()  # clear retained state
        print('execution complete')
