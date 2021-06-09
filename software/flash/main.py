# BuoyControllerAsync v1.1
# main.py
# MIT license; Copyright (c) 2020 Andrea Corbo

import uasyncio as asyncio
from sched.sched import schedule
from primitives.message import Message
import time
import gc
import select
import machine
import pyb
import session
import menu
from tools.utils import iso8601, scheduling, alert, log, welcome_msg, blink, msg, timesync, disconnect, trigger
from configs import dfl, cfg

devs = []

async def hearthbeat():
    await scheduling.wait()
    while 1:
        print('alive!')
        await asyncio.sleep(1)

async def restart():
    machine.reset()

async def cleaner():
    while True:
        gc.collect()
        gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
        await asyncio.sleep(1)

# Listens on uart / usb.
async def listner(trigger):
    global devs
    m = Message()
    trigger.set(True)
    async def poller(stream):
        sreader = asyncio.StreamReader(stream)
        i=0
        while True:
            await scheduling.wait() #and await disconnect.wait()
            b = await sreader.read(1)
            if b:
                try:
                    b.decode('utf-8')
                except UnicodeError:
            	    await asyncio.sleep(0)
            	    continue
                if (b == dfl.ESC_CHAR.encode() and stream.__class__.__name__ == 'UART' and not session.logging):
                    i += 1
                    if i > 2:
    					asyncio.create_task(session.login(m,stream))
    					session.logging = True
                elif (b == b'\x1b' and (stream.__class__.__name__ == 'UART' and session.loggedin or stream.__class__.__name__ == 'USB_VCP') and not menu.interactive):
                    asyncio.create_task(menu.main(m,stream,devs))
                    m.set(b)  # Passes ESC to menu.
                    menu.interactive = True
                else:
                    m.set(b)
                    i=0
            await asyncio.sleep_ms(100)
    asyncio.create_task(poller(pyb.USB_VCP()))  # Polls the usb vcp.
    while True:
        await trigger.wait()
        if trigger.value():
            polluart = asyncio.create_task(poller(pyb.UART(3,9600)))  # Polls the modem uart.
        else:
            polluart.cancel()
        trigger.clear()
        await asyncio.sleep_ms(100)

# Sends an sms as soon is generated.
async def alerter(txt):
    while True:
        await txt
        for num in cfg.SMS_RECIPIENTS:
            await modem.sms(txt.value(), num)
            await asyncio.sleep(0.5)
        txt.clear()
        await asyncio.sleep(0)

# Launches devs tasks.
async def launcher(obj,tasks):
    if scheduling.is_set():  # Pauses scheduler.
        if tasks:
            asyncio.create_task(obj.main(tasks))
        else:
            asyncio.create_task(obj.main())

async def main():

    # Creates devs objects.
    global devs
    msg(' INIT DEVICES ')
    for i in reversed(range(len(dfl.DEVS))):  # Gps first!
        if dfl.DEVS[i]:
            dev = dfl.DEVS[i]
        elif cfg.DEVS[i]:
            dev = cfg.DEVS[i]
        else:
            continue
        exec('import ' + dev.split('.')[0])
        exec(dev.split('.')[1].lower() + '=' + dev + '()')
        devs.append(eval(dev.split('.')[1].lower()))
        await asyncio.sleep(0)
    await asyncio.sleep(1)  # Waits 1 second to allow devs properly power on.
    # Executes devs startup routines.
    init_tasks = []
    for dev in devs:
        init_tasks.append(asyncio.create_task(dev.startup()))
        await asyncio.sleep(0)
    # Waits until all instruments have been started up.
    await asyncio.gather(*init_tasks, return_exceptions=True)

    # Initialises the scheduler.
    msg(' START SCHEDULER ')
    scheduling.set()
    #disconnect.set()
    for c in cfg.CRON:
        asyncio.create_task(schedule(
            launcher,
            eval(c[0]), # device object
            c[1],       # device tasks
            wday=c[-7],
            month=c[-6],
            mday=c[-5],
            hrs=c[-4],
            mins=c[-3],
            secs=c[-2],
            times=c[-1]
            ))
    # asyncio.create_task(schedule(restart, hrs=23, mins=56, secs=00))  # restart the system daily.
    while True:
        await asyncio.sleep(60)  # Keeps scheduler running forever.

############################ Program starts here ###############################
log(dfl.RESET_CAUSE[machine.reset_cause()], type='e')
welcome_msg()
asyncio.create_task(blink(4, 1, 2000, stop_evt=timesync))  # Blue, no gps fix.
asyncio.create_task(blink(3, 100, 1000, cancel_evt=scheduling))  # Yellow, initialisation.
asyncio.create_task(blink(2, 1, 2000, start_evt=timesync))  # Green, operating.
asyncio.create_task(cleaner())
asyncio.create_task(listner(trigger))
asyncio.create_task(alerter(alert))

try:
    asyncio.run(main())
    loop.set_exception_handler(_handle_exception)
except KeyboardInterrupt:
    pass
finally:
    asyncio.new_event_loop()  # Clear retained state.
