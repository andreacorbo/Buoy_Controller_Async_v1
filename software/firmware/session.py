# session.py
# MIT license; Copyright (c) 2020 Andrea Corbo

import uasyncio as asyncio
import time
import select
import pyb
from configs import dfl

logging = False
loggedin = False

async def login(msg,uart):
    global logging, loggedin

    async def expire():
        global logging, loggedin
        await asyncio.sleep(dfl.SESSION_TIMEOUT)
        uart.write('SESSION EXPIRED.\r\n')
        pyb.repl_uart(None)
        logging = False
        loggedin = False
        await asyncio.sleep(0)

    for i in range(dfl.LOGIN_ATTEMPTS):
        uart.write('ENTER PASSWORD:')
        msg.clear()  # Discards last char.
        buff = bytearray()
        while True:
            await msg
            if msg.value() == b'\r':
                if buff.decode() == dfl.PASSWD:
                    asyncio.create_task(expire())
                    uart.write('\n\rAUTH OK.\r\n')
                    pyb.repl_uart(uart)
                    loggedin = True
                    msg.clear()
                    return
                elif i < dfl.LOGIN_ATTEMPTS - 1:
                    uart.write('\r\nTRY AGAIN.\n\r')
                    msg.clear()
                    break
                else:
                    uart.write('\r\nAUTH FAILED.\n\r')
                    logging = False
                    msg.clear()
                    return
            else:
                uart.write(b'*')
                buff.extend(msg.value())
            msg.clear()
            await asyncio.sleep(0)
        await asyncio.sleep(0)
