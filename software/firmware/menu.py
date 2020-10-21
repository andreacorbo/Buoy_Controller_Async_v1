# menu.py
# MIT license; Copyright (c) 2020 Andrea Corbo

import uasyncio as asyncio
import os
import select
import pyb
from tools.utils import scheduling, logger, read_cfg, iso8601
from configs import dfl, cfg

interactive = False

ESC = b'\x1b'
BACKSPACE = b'\x7f\x08'
RETURN = b'\x0d'
SPACE = b'\x20'

async def main(msg,uart,objs):
    global interactive
    board = False
    devices = False
    device = False
    dev = None
    logger = False  # Stops log stream.
    while True:
        await msg
        if not board:
            if not devices:
                if not device:
                    if msg.value() == ESC:
                        board = True
                        await board_menu()
                else:  # device
                    if msg.value() == ESC:
                        await device_menu(dev)
                    elif  msg.value() == b'0':
                        dev.toggle()
                        await device_menu(dev)
                    elif  msg.value() == b'1':
                        await pass_through(dev,uart)
                        await device_menu(dev)
                    elif  msg.value() == b'2':
                        pass
                    elif  msg.value() == b'3':
                        await get_config(dev)
                        await device_menu(dev)
                    elif msg.value() in BACKSPACE:
                        device = False
                        devices = True
                        await devices_menu(objs)
            else:  # devices
                if msg.value() == ESC:
                    await devices_menu(objs)
                elif msg.value() in BACKSPACE:
                    devices = False
                    board = True
                    await board_menu()
                else:
                    devices = False
                    device = True
                    try:
                        dev = objs[int(msg.value())]
                        await device_menu(dev)
                    except IndexError:
                        await devices_menu(objs)
        else:  # board
            if msg.value() == ESC:
                board = True
                await board_menu()
            elif msg.value() == b'0':
                board  = False
                devices = True
                await devices_menu(objs)
            elif msg.value() == b'1':
                await data_files()
                await board_menu()
            elif msg.value() == b'2':
                await last_log()
                await board_menu()
            elif msg.value() in BACKSPACE:
                interactive = False
                logger = True
                msg.clear()
                return
        msg.clear()
        await asyncio.sleep(0)

async def board_menu():
    print("\r\n".join([
    "{:#^40}".format(" BOARD "),
    "[0] DEVICES",
    "[1] DATA FILES",
    "[2] LAST LOG",
    "[BACKSPACE] BACK TO SCHEDULED MODE",
    "\r"]))
    await asyncio.sleep(0)

async def devices_menu(objs):
    _ = ["{:#^40}".format(" DEVICES ")]
    for obj in objs:
        _.append("[{}] {}".format(objs.index(obj), obj.name))
        await asyncio.sleep(0)
    _.extend([
    "[BACKSPACE] BACK",
    "\r"])
    print("\r\n".join(_))

async def device_menu(obj):
    _ = ["{:#^40}".format(" "+obj.name+" ")]
    if hasattr(obj,"gpio"):
        _.append("[0] ON/OFF ({})".format(dfl.STATUS[obj.gpio.value()]))
    if hasattr(obj,"uart"):
        _.append("[1] TRANSPARENT MODE")
    _.extend([
    "[2] SAMPLING",
    "[3] CONFIGURATION",
    "[BACKSPACE] BACK",
    "\r"])
    print("\r\n".join(_))
    await asyncio.sleep(0)

async def get_config(obj):
    _ = ["{:#^40}".format(" CONFIGURATION ")]
    cfg = read_cfg(obj.name.split('.')[0])[obj.name.split('.')[1]]
    for k in sorted(cfg):
        if type(cfg[k]).__name__ == 'dict':
            for kk in sorted(cfg[k]):
                _.append("  {: <20}{}".format(kk,cfg[k][kk]))  # TODO iterate subitems.
                await asyncio.sleep(0)
        else:
            _.append("{: <22}{}".format(k,cfg[k]))
        #if scheduling.is_set():
        await asyncio.sleep(0)
    _.append("\r")
    print("\r\n".join(_))

async def pass_through(obj,uart):
    scheduling.clear()
    print('[P] PAUSE/RESUME\r\n[BACKSPACE] BACK\r\n')
    running = asyncio.Event()  # manages scheduler.
    running.set()  # enable scheduler
    obj.init_uart()
    tx = bytearray()
    _poll = select.poll()  # Creates a poll object to listen to.
    _poll.register(uart, select.POLLIN)
    _poll.register(pyb.USB_VCP(), select.POLLIN)
    _poll.register(obj.uart, select.POLLIN)
    while True:
        poll = _poll.ipoll(0, 0)
        for stream in poll:
            byte = stream[0].read(1)
            try:
                byte.decode('utf-8')
            except UnicodeError:
                continue
            if stream[0] in [uart,pyb.USB_VCP()]:
                if byte in BACKSPACE:  # [BACKSPACE] Backs to previous menu.
                    obj.uart.deinit()
                    scheduling.set()
                    return
                elif byte == SPACE:  # [SPACE] Pauses and resumes.
                    if running.is_set():
                        print('[SPACE] PAUSE\RESUME')
                        running.clear()
                    else:
                        running.set()
                elif byte == RETURN:  # [CR] Forwards cmds to device.
                    tx.extend(byte)
                    obj.uart.write(tx)
                    tx = bytearray()
                else:
                    tx.extend(byte)
                    print(byte.decode('utf-8'), end='')
            elif running.is_set():
                 print('{}'.format(byte.decode('utf-8')), end='')
            await asyncio.sleep(0)
        await asyncio.sleep(0)

async def data_files():
    _ = ["{:#^40}".format(" DATA FILES ")]
    try:
        data = os.listdir(dfl.DATA_DIR)
        data.sort(reverse=True)
    except:
        data = []
    size = 0
    for f in data:
        stat = os.stat(dfl.DATA_DIR + "/" + f)
        size += stat[6]//1024
        _.append("{: <5} {: <20} {}".format(str(stat[6]//1024), iso8601(stat[7]), f))
        await asyncio.sleep(0)
    fsstat = os.statvfs(dfl.DATA_DIR)
    _.append("{} Files {}/{} kB".format(len(data), str(size), str(fsstat[2]*fsstat[0]//1024)))
    _.append("\r")
    print("\r\n".join(_))

async def last_log():
    _ = ["{:#^40}".format(" LAST LOG ")]
    with open(dfl.LOG_DIR + '/' + dfl.LOG_FILE,"r") as l:
        for i in range(dfl.LOG_LINES):
            _.append(l.readline()[:-2])
            await asyncio.sleep(0)
    _.append("\r")
    print("\r\n".join(_))
