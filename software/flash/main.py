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
# Devices objects.
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
        print('{} alive!'.format(utils.timestring(time.time())))
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
    ptr = 0
    txts = []
    def get_last_byte():
        nonlocal ptr
        try:
            with open('/sd/sms/.sms') as t:
                ptr = int(t.read())
        except:
            ptr = 0
        threadlock.set()

    def reader():
        nonlocal ptr, txts
        with open('/sd/sms/sms') as s:
            print(ptr)
            s.seek(ptr)
            for l in s:
                txts.append(l)
                #await modem.sms(l, m_semaphore)
            ptr = s.tell()
        threadlock.set()

    def set_last_byte():
        nonlocal ptr
        with open('/sd/sms/.sms', 'w') as t:
            t.write(str(ptr))
        threadlock.set()

    while True:
        await utils.sms_queue.wait()
        _thread.start_new_thread(get_last_byte, ())  # Gets ptr from tmp file.
        await asyncio.sleep_ms(10)
        await threadlock.wait()
        threadlock.clear()
        _thread.start_new_thread(reader, ())  # Reads out lines and send sms.
        await asyncio.sleep_ms(10)
        await threadlock.wait()
        threadlock.clear()
        for t in txts:
            await modem.sms(t, m_semaphore)
            await asyncio.sleep(0)
        _thread.start_new_thread(set_last_byte, ())  # Sets ptr in tmp file.
        await asyncio.sleep_ms(10)
        await threadlock.wait()
        threadlock.clear()
        utils.sms_queue.clear()


async def run(obj,tasks=[],lock=None):
    # Launches coros.
    if scheduling.is_set():  # Pauses scheduler.
        asyncio.create_task(obj.main(lock, tasks))

utils.log(dfl.RESET_CAUSE[machine.reset_cause()], type='e')
utils.welcome_msg()

async def dummy():
    rtc=pyb.RTC()
    rtc.datetime((2020,10,04,0,11,00,00,000))

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
    init_tasks = []
    for dev in devices:
        if dev.__qualname__ in ('GPS','METEO'):
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
            wday=task[len(task)-7],
            month=task[len(task)-6],
            mday=task[len(task)-5],
            hrs=task[len(task)-4],
            mins=task[len(task)-3],
            secs=task[len(task)-2],
            times=task[len(task)-1]
            ))
    asyncio.create_task(hearthbeat())
    asyncio.create_task(smsender())
    #asyncio.create_task(writer())
    await asyncio.sleep(2)
    #asyncio.create_task(modem.data_transfer(f_lock, m_semaphore))
    asyncio.create_task(schedule(modem.data_transfer, f_lock, m_semaphore, hrs=None, mins=(0, 30)))
    #asyncio.create_task(schedule(meteo.main, f_lock, ['log'], hrs=None, mins=range(0, 60, 2)))
    asyncio.create_task(schedule(dummy, None, None, hrs=None, mins=20))
#
# Loop forever...
#
try:
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    loop.run_forever()
except KeyboardInterrupt:
    #loop.stop()
    pass
finally:
    asyncio.new_event_loop()  # Clear retained state
