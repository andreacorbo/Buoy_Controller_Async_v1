import uasyncio as asyncio
import pyb
import json
import os
import time
from configs import dfl, cfg
from primitives.message import Message

logger = True  # Prints out messages.

sms = Message()  # Sms event.

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

def verbose(msg):
    if cfg.VERBOSE:
        print(msg)

def read_cfg(file):
    try:
        with open(dfl.CONFIG_DIR + file + dfl.CONFIG_TYPE) as cfg:
            return json.load(cfg)
    except:
        log('Unable to read file {}'.format(file), type='e')

def unix_epoch(epoch):
    # Converts embedded epoch 2000-01-01 00:00:00 to unix epoch 1970-01-01 00:00:00.
    return 946684800 + epoch

def iso8601(timestamp):
    # YYYY-MM-DD HH:MM:SS
    return '{}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z'.format(time.localtime(timestamp)[0], time.localtime(timestamp)[1], time.localtime(timestamp)[2], time.localtime(timestamp)[3], time.localtime(timestamp)[4], time.localtime(timestamp)[5])

async def blink(led,dutycycle=50,period=1000, **kwargs):
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
        onperiod = period//100*dutycycle
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
    type = 'm'
    if kwargs and 'type' in kwargs:
        type = kwargs['type']
    timestamp = iso8601(time.time())
    if logger:  # Global flag.
        print('{: <22}{: <8}{}'.format(timestamp, args[0], ' '.join(map(str, args[1:]))))
    if cfg.LOG_TO_FILE:
        if type in cfg.LOG_LEVEL:
            try:
                with open(dfl.LOG_DIR + '/' + dfl.LOG_FILE, 'a') as f:  # TODO: start new file, zip old file, remove oldest
                    f.write('{},{},{}\r\n'.format(timestamp, args[0], ' '.join(map(str, args[1:]))))
            except Exception as err:
                print(err)

def set_sms(text):
    # Set sms text, works one-to-one with smsender.
    global sms
    sms.set(text)

def log_data(data):
    try:
        with open(dfl.DATA_DIR + '/' + cfg.DATA_FILE, 'a') as data_file:
            data_file.write('{}\r\n'.format(data))
        log(data)
    except Exception as err:
        log(type(err).__name__, err, type='e')  # DEBUG

def files_to_send():

    def too_old(file):
        filename = file.split('/')[-1]
        path = file.replace('/' + file.split('/')[-1], '')
        if time.mktime(time.localtime()) - time.mktime([int(filename[0:4]),int(filename[4:6]),int(filename[6:8]),0,0,0,0,0]) > cfg.BUF_DAYS * 86400:
            os.rename(file, path + '/' + dfl.SENT_FILE_PFX + filename)
            if path + '/' + dfl.TMP_FILE_PFX + filename in os.listdir(path):
                os.remove(path + '/' + dfl.TMP_FILE_PFX + filename)
            return True
        return False

    for file in sorted(os.listdir(dfl.DATA_DIR)):
        if file[0] not in (dfl.TMP_FILE_PFX, dfl.SENT_FILE_PFX):  # check for unsent files
            try:
                int(file)
            except:
                os.remove(dfl.DATA_DIR + '/' + file)  # Deletes all except data files.
                continue
            if not too_old(dfl.DATA_DIR + '/' + file):
                # Checks if new data has been added to the file since the last transmission.
                pointer = 0
                try:
                    with open(dfl.DATA_DIR + '/' + dfl.TMP_FILE_PFX + file, 'r') as tmp:
                        pointer = int(tmp.read())
                except:
                    pass  # Tmp file does not exist.
                if os.stat(dfl.DATA_DIR + '/' + file)[6] > pointer:
                    #unsent_files.append(config.DATA_DIR + '/' + file)  # Makes a list of files to send.
                    yield dfl.DATA_DIR + '/' + file
    if any(file[0] not in (dfl.TMP_FILE_PFX, dfl.SENT_FILE_PFX) for file in os.listdir(dfl.DATA_DIR)):
            yield '\x00'  # Needed to end ymodem transfer.
