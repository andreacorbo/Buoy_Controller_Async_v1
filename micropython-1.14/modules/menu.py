# menu.py
# MIT license; Copyright (c) 2020 Andrea Corbo

import uasyncio as asyncio
from primitives.message import Message
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
    fw = Message()  # Forwards main uart to device.
    while True:
        await msg
        fw.set(msg.value())
        if not board:
            if not devices:
                if not device:
                    if msg.value() == ESC:
                        board = True
                        await board_menu()
                else:  # device
                    if  msg.value() == b'0':
                        dev.toggle()
                        await device_menu(dev)
                    elif msg.value() == b'1':
                        fw.clear()  # Clears last byte.
                        asyncio.create_task(pass_through(dev,uart,fw))
                        #await device_menu(dev)
                    elif  msg.value() == b'2':
                        pass
                    elif  msg.value() == b'3':
                        await get_config(dev)
                        await device_menu(dev)
                    elif msg.value() in BACKSPACE:
                        device = False
                        devices = True
                        await devices_menu(objs)
                    elif msg.value() == ESC:
                        await device_menu(dev)
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
                    except:
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

async def pass_through(device,uart,fw):
    cancel = asyncio.Event()  # Task cancellation event.
    device.init_uart()
    dreader = asyncio.StreamReader(device.uart)
    dwriter = asyncio.StreamWriter(device.uart,{})
    mwriter = asyncio.StreamWriter(uart,{})

    async def send(dwriter, fw):
        b = bytearray()
        while True:
            await fw
            if fw.value() == ESC:
                cancel.set()
            else:
                print(fw.value().decode(),end='')
                b.append(ord(fw.value()))
                if fw.value() == b'\r':
                    await dwriter.awrite(b)
                    b = bytearray()
                fw.clear()
            await asyncio.sleep(0)

    async def recv(dreader, mwriter):
        while True:
            res = await dreader.readline()
            if res is not None:
                await mwriter.awrite(res)
            await asyncio.sleep(0)

    send_ = asyncio.create_task(send(dwriter, fw))
    recv_ = asyncio.create_task(recv(dreader, mwriter))
    await cancel.wait()
    send_.cancel()
    recv_.cancel()
    return

    '''while True:
        if fw.is_set():
            print(fw.value())
            if fw.value() == ESC:
                return
            try:
                await asyncio.wait_for(dwriter.awrite(fw.value()), 1)
                fw.clear()
            except asyncio.TimeoutError:
                await mwriter.awrite('timeout writing to device')

        try:
            res = await asyncio.wait_for(dreader.readline(),2)
            if res is not None:
                await mwriter.awrite(res)
        except asyncio.TimeoutError:
            await mwriter.awrite('timeout reading from device')
            #return
        await asyncio.sleep(0)'''

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
