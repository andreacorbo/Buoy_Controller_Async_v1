import uasyncio as asyncio
from sched.sched import schedule
from primitives.semaphore import Semaphore
from primitives.message import Message
import time
import gc
import select
import machine
import pyb
import _thread
import session
import menu
import tools.utils as utils
from configs import dfl, cfg
#
# Primitives.
#
f_lock = asyncio.Lock()  # Data file lock.
m_semaphore = Semaphore()  # Data/Sms semaphore.
scheduling = asyncio.Event()  # Scheduler event.
time_sync = asyncio.Event()  # Time Sync event.
s_lock = asyncio.Lock()  # Sms file lock.
threadlock = asyncio.Event()  # Threadlock event.
g_semaphore = Semaphore()  # Gps/Meteo semaphore.

#
# DEBUG
#
async def hearthbeat():
    # Prints out 'alive!' msg.
    while True:
        print('{} alive!'.format(utils.iso8601(time.time())))
        await asyncio.sleep(5)

async def garbage():
    # Frees ram.
    while True:
        gc.collect()
        gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
        await asyncio.sleep(1)

async def receiver():
    # Listens on uart / usb.
    msg = Message()
    uart = pyb.UART(3,9600)
    poll_ = select.poll()  # Creates a poll object to listen to.
    poll_.register(uart, select.POLLIN)
    poll_.register(pyb.USB_VCP(), select.POLLIN)
    i=0
    while True:
        await scheduling.wait()
        poll = poll_.ipoll(0, 0)
        for stream in poll:
            byte = stream[0].read(1)
            try:
                byte.decode('utf-8')
            except UnicodeError:
                continue
            if byte == dfl.ESC_CHAR.encode() and stream[0] == uart and not session.logging:
                i += 1
                if i > 2:
                    asyncio.create_task(session.login(msg,uart))
                    session.logging = True
            elif byte == b'\x1b' and (stream[0] == uart and session.loggedin or stream[0] != uart) and not menu.interactive:
                asyncio.create_task(menu.main(msg,uart,devices,scheduling))
                msg.set(byte)  # Passes ESC to menu.
                menu.interactive = True
            else:
                msg.set(byte)
                i=0
        await asyncio.sleep(0)

async def smsender():
    # Wait for message from utils.set_sms
    await utils.sms
    await modem.sms(utils.sms.value(), m_semaphore)
    utils.sms.clear()

async def run(obj,tasks=[],lock=None):
    # Launches coros.
    if scheduling.is_set():  # Pauses scheduler.
        asyncio.create_task(obj.main(lock, tasks))

def _handle_exception(loop, context):
    import sys
    print('Global handler')
    sys.print_exception(context["exception"])
    loop.stop()
    #sys.exit()  # Drastic - loop.stop() does not work when used this way

utils.log(dfl.RESET_CAUSE[machine.reset_cause()], type='e')
utils.welcome_msg()
#
# Main.
#
async def main():
    #async def feed_(wdt):
    #    # Periodically feeds the watchdog timer.
    #    while True:
    #        wdt.feed()
    #        utils.log('feeding the wdt...')
    #        await asyncio.sleep_ms(dfl.WD_TIMEOUT - 5000)
    #wdt = machine.WDT(timeout=dfl.WD_TIMEOUT)
    #asyncio.create_task(feed_(wdt))
    asyncio.create_task(garbage())  # Starts up garbage collection.
    #asyncio.create_task(receiver()) # Starts up receiver.
    #
    # Leds behaviour.
    #
    # Blue, waiting for gps fix.
    asyncio.create_task(utils.blink(4, 1, 2000, stop_evt=time_sync))
    # Yellow, initialisation sequence.
    asyncio.create_task(utils.blink(3, 100, 1000, cancel_evt=scheduling))
    # Green, hearthbeat.
    asyncio.create_task(utils.blink(2, 1, 2000, start_evt=time_sync))
    #
    # Initializes the instruments.
    #
    utils.msg(' INIT DEVICES ')
    #
    # Creates devices objects.
    #
    devices = []
    for i in range(len(dfl.DEVS)):
        if dfl.DEVS[i]:
            dev = dfl.DEVS[i]
        elif cfg.DEVS[i]:
            dev = cfg.DEVS[i]
        else:
            continue
        exec('import ' + dev.split('.')[0])
        exec(dev.split('.')[1].lower() + '=' + dev + '()')
        devices.append(eval(dev.split('.')[1].lower()))
    await asyncio.sleep(1)
    #
    # Executes devices start_up routines.
    #
    init_tasks = []
    for dev in devices:
        if dev in (gps, meteo):
            init_tasks.append(asyncio.create_task(dev.start_up(time_sync=time_sync,sema=g_semaphore)))
        else:
            init_tasks.append(asyncio.create_task(dev.start_up(time_sync=time_sync)))
    await asyncio.gather(*init_tasks, return_exceptions=True)  # Waits until all instruments have been started up.
    #
    # initializes the scheduler.
    #
    utils.msg(' START SCHEDULER ')
    scheduling.set()
    for task in cfg.CRON:
        asyncio.create_task(schedule(
            run,                                    # launcher
            eval(task[0]),                          # device object
            task[1],                                # device tasks
            eval(task[2]) if task[2] else task[2],  # file lock
            wday=task[-7],
            month=task[-6],
            mday=task[-5],
            hrs=task[-4],
            mins=task[-3],
            secs=task[-2],
            times=task[-1]
            ))
    asyncio.create_task(hearthbeat())
    asyncio.create_task(smsender())
    #asyncio.create_task(schedule(modem.data_transfer, f_lock, m_semaphore, mins=range(0, 60, 10), secs=0))
#
# Loop forever...
#
try:
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(_handle_exception)
    loop.create_task(main())
    loop.run_forever()
except KeyboardInterrupt:
    pass
finally:
    asyncio.new_event_loop()  # Clear retained state
