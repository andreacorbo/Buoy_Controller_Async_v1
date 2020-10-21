# tools/utils.py
# MIT license; Copyright (c) 2020 Andrea Corbo

import uasyncio as asyncio
from primitives.message import Message
from primitives.semaphore import Semaphore
import time
import os
import json
import _thread
import pyb
from configs import dfl, cfg

logger = True  # Prints out messages.

f_lock = asyncio.Lock()  # Data file lock.
alert = Message()  # Sms message.
timesync = asyncio.Event()  # Gps fix event.
scheduling = asyncio.Event()  # Scheduler event.
disconnect = asyncio.Event()  # Modem event.

def welcome_msg():
    print(
    '{:#^80}\n\r#{: ^78}#\n\r#{: ^78}#\n\r# {: <20}{: <57}#\n\r# {: <20}{: <57}#\n\r# {: <20}{: <57}#\n\r# {: <20}{: <57}#\n\r{:#^80}'.format(
        '',
        'WELCOME TO ' + cfg.HOSTNAME + ' ' + dfl.SW_NAME + ' ' + dfl.SW_VERSION,
        '',
        ' current time:',
        iso8601(time.time()),
        ' machine:',
        os.uname()[4],
        ' mpy release:',
        os.uname()[2],
        ' mpy version:',
        os.uname()[3],
        ''))

# Prints out extensive messages.
def verbose(msg):
    if cfg.VERBOSE:
        print(msg)

# Reads out an device config file.
def read_cfg(file):
    try:
        with open(dfl.CONFIG_DIR + file + dfl.CONFIG_TYPE) as cfg:
            return json.load(cfg)
    except:
        log('Unable to read file {}'.format(file), type='e')

# Converts embedded epoch 2000-01-01T00:00:00Z to unix epoch 1970-01-01T00:00:00Z.
def unix_epoch(epoch):
    return 946684800 + epoch

# Formats utc dates according to iso8601 standardization yyyy-mm-ddThh:mm:ssZ
def iso8601(timestamp):
    return '{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z'.format(
    time.localtime(timestamp)[0],
    time.localtime(timestamp)[1],
    time.localtime(timestamp)[2],
    time.localtime(timestamp)[3],
    time.localtime(timestamp)[4],
    time.localtime(timestamp)[5])

async def blink(led, dutycycle=50 ,period=1000 , **kwargs):
    while True:
        if kwargs and 'cancel_evt' in kwargs and kwargs['cancel_evt'].is_set():
            await asyncio.sleep(0)
            return
        if kwargs and 'stop_evt' in kwargs:
            while kwargs['stop_evt'].is_set():
                await asyncio.sleep(0)
                continue
        if kwargs and 'start_evt' in kwargs:
            await kwargs['start_evt'].wait()
        onperiod = period // 100 * dutycycle
        pyb.LED(led).on()
        await asyncio.sleep_ms(onperiod)
        pyb.LED(led).off()
        await asyncio.sleep_ms(period - onperiod)

def msg(msg=None):
    if msg is None:
        print('')
    elif msg == '-':
        print('{:#^80}\n'.format(''))
    else:
        print('\n{:#^80}'.format(msg))

def log(*args, **kwargs):
    #evt = asyncio.Event()  # Event to wait for thread completion.
    def fwriter():
        try:
            with open(dfl.LOG_DIR + '/' + dfl.LOG_FILE, 'a') as f:
                f.write('{},{},{}\r\n'.format(
                timestamp,
                args[0],
                ' '.join(map(str, args[1:]))))
        except Exception as err:
            print(err)
        #evt.set()

    type = 'm'
    if kwargs and 'type' in kwargs:
        type = kwargs['type']
    timestamp = iso8601(time.time())
    if logger:  # Global flag.
        print('{: <22}{: <8}{}'.format(
        timestamp, args[0],
        ' '.join(map(str, args[1:]))))
    if cfg.LOG_TO_FILE:
        if type in cfg.LOG_LEVEL:
            _thread.start_new_thread(fwriter,())
            #await asyncio.sleep_ms(10)
            #await evt.wait()
            #evt.clear()

# Set alert msg, caught by alerter.
def set_alert(text):
    global alert
    alert.set(text)

def dailyfile():
    # YYYYMMDD
    return '{:04d}{:02d}{:02d}'.format(
        time.localtime()[0],
        time.localtime()[1],
        time.localtime()[2]
        )

async def log_data(data):
    global f_lock
    evt = asyncio.Event()  # Event to wait for thread completion.
    def fwriter():
        try:
            with open(dfl.DATA_DIR + '/' + dailyfile(), 'a') as f:
                f.write('{}\r\n'.format(data))
                log(data)
        except Exception as err:
            log(type(err).__name__, err, type='e')
        evt.set()

    async with f_lock:
        _thread.start_new_thread(fwriter, ())
        await asyncio.sleep_ms(10)
        await evt.wait()
        evt.clear()

def files_to_send():
    for f in sorted(os.listdir(dfl.DATA_DIR)):
        try:
            int(f)  # Names of unsent datafiles are integer YYYYMMDD.
        except ValueError:
            continue
        if (time.mktime(time.localtime())
            - time.mktime([int(f[0:4]),int(f[4:6]),int(f[6:8]),0,0,0,0,0])
            < cfg.BUF_DAYS * 86400):
            yield dfl.DATA_DIR + '/' + f  # Skips files older than BUF_DAYS.
    if dfl.LOG_FILE in os.listdir(dfl.LOG_DIR):
        yield dfl.LOG_DIR + '/' + dfl.LOG_FILE  # Sends last log file.
    yield '\x00'  # Null file is needed to end ymodem transmission.
