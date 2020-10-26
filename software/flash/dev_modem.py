# dev_modem.py
# MIT license; Copyright (c) 2020 Andrea Corbo
#"Init_Ats":["ATE1\r","ATI\r","AT+CREG=0\r","AT+CSQ\r","AT+CBST=7,0,1\r","AT+COPS=1,2,22201\r","ATS0=1\r","AT&W\r"],
import uasyncio as asyncio
from primitives.semaphore import Semaphore
import time
from tools.utils import log, verbose, files_to_send, disconnect
from configs import dfl, cfg
from device import DEVICE
from tools.ymodem import YMODEM

class MODEM(DEVICE, YMODEM):

    def __init__(self):
        DEVICE.__init__(self)
        self.sreader = asyncio.StreamReader(self.uart)
        self.swriter = asyncio.StreamWriter(self.uart, {})
        self.data = b''
        self.semaphore = Semaphore()  # Data/Sms semaphore.
        self.disconnect = disconnect
        self.at_timeout = self.config['Modem']['At_Timeout']
        self.init_ats = self.config['Modem']['Init_Ats']
        self.init_timeout = self.config['Modem']['Init_Timeout']
        self.call_ats = self.config['Modem']['Call_Ats']
        self.hangup_ats = self.config['Modem']['Hangup_Ats']
        self.at_delay = self.config['Modem']['At_Delay']
        self.call_attempt = self.config['Modem']['Call_Attempt']
        self.call_delay = self.config['Modem']['Call_Delay']
        self.call_timeout = self.config['Modem']['Call_Timeout']
        self.ymodem_delay = self.config['Modem']['Ymodem_Delay']
        self.keep_alive = self.config['Modem']['Keep_Alive']
        self.sms_ats = self.config['Modem']['Sms_Ats']
        self.sms_to = self.config['Modem']['Sms_To']
        self.sms_timeout = self.config['Modem']['Sms_Timeout']
        YMODEM.__init__(self, self.agetc, self.aputc)

    async def startup(self, **kwargs):
        self.on()
        self.init_uart()
        if await self.is_ready():
            await self.init()

    def decode(self):
        try:
            return self.data.decode('utf-8')
        except UnicodeError:
            log(self.__qualname__, 'communication error')
            return False

    # Captures commands replies.
    async def reply(self):
        self.data = b''
        try:
            self.data = await asyncio.wait_for(self.sreader.readline(), self.reply_timeout)
            if self.decode():
                return True
        except asyncio.TimeoutError:
            log(self.__qualname__, 'no answer')
        return False

    # Sends ats commands.
    async def cmd(self, cmd):
        await self.swriter.awrite(cmd)
        while await self.reply():
            verbose(self.data)
            if (self.data.startswith(b'OK')
                or self.data.startswith(b'ERROR')
                or self.data.startswith(b'NO CARRIER')
                or self.data.startswith(b'CONNECT')
                ):
                return True
            await asyncio.sleep(0)
        return False

    # Waits for modem getting ready.
    async def is_ready(self):
        self.reply_timeout = self.at_timeout
        t0 = time.time()
        while time.time() - t0 < self.init_timeout:
            if await self.cmd('AT\r'):
                if self.data.startswith(b'OK'):
                    return True
            await asyncio.sleep(0)
        log(self.__qualname__, 'not ready')
        return False

    # Sends initialisation cmds.
    async def init(self):
        self.reply_timeout = self.at_timeout
        for at in self.init_ats:
            while True:
                if await self.cmd(at):
                    if self.data.startswith(b'OK'):
                        break
                    elif self.data.startswith(b'ERROR'):
                        await asyncio.sleep(self.at_delay)
                        continue
                log(self.__qualname__, 'initialisation failed')
                return
            await asyncio.sleep(self.at_delay)
        log(self.__qualname__, 'successfully initialised')

    async def agetc(self, size, timeout=1):
        try:
            return await asyncio.wait_for(self.sreader.readexactly(size), timeout)
        except asyncio.TimeoutError:
            return

    # Sends n-bytes.
    async def aputc(self, data, timeout=1):
        try:
            await asyncio.wait_for(self.swriter.awrite(data), timeout)
        except asyncio.TimeoutError:
            return 0
        return len(data)

    # Make a call.
    async def call(self):
        self.reply_timeout = self.call_timeout  # Takes in account the real call timeout.
        log(self.__qualname__, 'calling...')
        for at in self.call_ats:
            if await self.cmd(at):
                if self.data.startswith(b'CONNECT'):
                    #await self.sreader.read(1)  # Clears last byte.
                    return True
            await asyncio.sleep(self.at_delay)
        log(self.__qualname__, 'call failed')
        return False

    # hangs a call.
    async def hangup(self):
        self.reply_timeout = self.at_timeout
        log(self.__qualname__, 'hangup...')
        for at in self.hangup_ats:
            if await self.cmd(at):
                if self.data.startswith(b'OK'):
                    await asyncio.sleep(self.at_delay)
                    continue
            log(self.__qualname__, 'hangup failed')
            return False
        return True

    # Tells to remote who it is.
    async def preamble(self, retry=3, timeout=10):
        await asyncio.sleep(2)  # Safely waits for remote getting ready.
        ec = 0
        while ec < retry:
            if await self.aputc(cfg.HOSTNAME.lower()):
                verbose(cfg.HOSTNAME.lower() +' -->')
                try:
                    res = await asyncio.wait_for(self.sreader.readexactly(1), timeout)
                    if res == b'\x06':  # ACK
                        verbose('<-- ACK')
                        return True
                except asyncio.TimeoutError:
                    ec += 1
        return False

    # Sends and receives data.
    async def datacall(self):
        async with self.semaphore:
            self.disconnect.clear()
            self.init_uart()
            ca = 0  # Attempts counter.
            for _ in range(self.call_attempt):
                ca += 1
                if await self.call():
                    if (await self.preamble(self.call_attempt, self.at_timeout)  # Introduces itself.
                        and await self.asend(files_to_send())  # Puts files.
                        #and await self.arecv()  # Gets files.
                        or ca == self.call_attempt):
                        await asyncio.sleep(self.keep_alive)  # Awaits user interaction.
                        break
                    await self.hangup()
                else:
                    await asyncio.sleep(self.at_delay)
            self.off()  # Restarts device.
            await asyncio.sleep(2)
            self.on()
            self.disconnect.set()

    # Sends an sms.
    async def sms(self, text):
        async with self.semaphore:
            self.disconnect.clear()
            self.reply_timeout = self.at_timeout
            log(self.__qualname__,'sending sms...')
            for at in self.sms_ats:
                if not await self.cmd(at):
                    log(self.__qualname__,'sms failed', at)
                    self.disconnect.set()
                    return False
                await asyncio.sleep(self.at_delay)
            await self.swriter.awrite(self.sms_to)
            try:
                self.data = await asyncio.wait_for(self.sreader.readline(), self.reply_timeout)
            except asyncio.TimeoutError:
                log(self.__qualname__,'sms failed', self.sms_to)
                self.disconnect.set()
                return False
            if self.data.startswith(self.sms_to):
                verbose(self.data)
                try:
                    self.data = await asyncio.wait_for(self.sreader.read(2), self.reply_timeout)
                except asyncio.TimeoutError:
                    log(self.__qualname__,'sms failed')
                    self.disconnect.set()
                    return False
                if self.data.startswith(b'>'):
                    verbose(self.data)
                    await self.swriter.awrite(text+'\r\n')
                    try:
                        self.data = await asyncio.wait_for(self.sreader.readline(), 60)
                    except asyncio.TimeoutError:
                        log(self.__qualname__,'sms failed')
                        self.disconnect.set()
                        return False
                    if self.data.startswith(text):
                        verbose(self.data)
                        if await self.cmd('\x1a'):
                            self.disconnect.set()
                            return True
            log(self.__qualname__,'sms failed')
            self.disconnect.set()
            return False

    async def main(self, task='datacall'):
            if task == 'datacall':
                await self.datacall()
