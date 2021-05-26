# asynctest.py Demo of asynchronous code scheduling tasks with cron

# Copyright (c) 2020 Peter Hinch
# Released under the MIT License (MIT) - see LICENSE file

import uasyncio as asyncio
from sched.sched import schedule
from time import localtime

def foo(txt):  # Demonstrate callback
    yr, mo, md, h, m, s, wd = localtime()[:7]
    fst = 'Callback {} {:02d}:{:02d}:{:02d} on {:02d}/{:02d}/{:02d}'
    print(fst.format(txt, h, m, s, md, mo, yr))

async def bar(txt):  # Demonstrate coro launch
    yr, mo, md, h, m, s, wd = localtime()[:7]
    fst = 'Coroutine {} {:02d}:{:02d}:{:02d} on {:02d}/{:02d}/{:02d}'
    print(fst.format(txt, h, m, s, md, mo, yr))
    await asyncio.sleep(0)

async def main():
    print('Asynchronous test running...')
    asyncio.create_task(schedule(bar, '@min 17', hrs=0, mins=34, secs=30))
    asyncio.create_task(schedule(bar, 'every 2 secs', hrs=None, mins=None, secs=range(0,60,2)))

try:
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    loop.run_forever()
except KeyboardInterrupt:
    pass
finally:
    _ = asyncio.new_event_loop()  # Clear retained state
