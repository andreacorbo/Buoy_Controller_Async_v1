import uasyncio as asyncio
from primitives.semaphore import Semaphore
import time
import os  # DEBUG
from tools.utils import log, verbose, files_to_send
from configs import dfl, cfg
from device import DEVICE
from tools.ymodem import YMODEM

class MODEM(DEVICE, YMODEM):

    def __init__(self):
        DEVICE.__init__(self)
        self.sreader = asyncio.StreamReader(self.uart)
        self.swriter = asyncio.StreamWriter(self.uart, {})
        self.data = b''
        self.semaphore = Semaphore(1)  # Data/Sms semaphore.
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
        YMODEM.__init__(self, self.agetc, self.aputc, dfl.TMP_FILE_PFX, dfl.SENT_FILE_PFX, dfl.BKP_FILE_PFX, mode='Ymodem1k')

    async def start_up(self, **kwargs):
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

    async def reply(self):
        #
        # Captures commands replies.
        #
        self.data = b''
        try:
            self.data = await asyncio.wait_for(self.sreader.readline(), self.reply_timeout)
            if self.decode():
                return True
        except asyncio.TimeoutError:
            log(self.__qualname__, 'no answer')
        return False

    async def cmd(self, cmd):
        #
        # sends ats commands.
        #
        await self.swriter.awrite(cmd)
        while await self.reply():
            verbose(self.data)
            #if not self.data.startswith(cmd) and not self.data.startswith('\r\n'):
            if self.data.startswith('OK') or self.data.startswith('ERROR') or self.data.startswith('NO CARRIER') or self.data.startswith('CONNECT'):
                return True
            await asyncio.sleep(0)
        return False

    async def is_ready(self):
        #
        # Waits for modem getting ready.
        #
        self.reply_timeout = self.at_timeout
        t0 = time.time()
        while time.time() - t0 < self.init_timeout:
            if await self.cmd('AT\r'):
                if self.data.startswith('OK'):
                    return True
            await asyncio.sleep(0)
        log(self.__qualname__, 'not ready')
        return False

    async def init(self):
        #
        # Sends initialisation cmds.
        #
        self.reply_timeout = self.at_timeout
        for at in self.init_ats:
            while True:
                if await self.cmd(at):
                    if self.data.startswith('OK'):
                        break
                    elif self.data.startswith('ERROR'):
                        await asyncio.sleep(self.at_delay)
                        continue
                log(self.__qualname__, 'initialisation failed')
                return
            await asyncio.sleep(self.at_delay)
        log(self.__qualname__, 'successfully initialised')

    async def agetc(self, size, timeout=1):
        try:
            if size:
                return await asyncio.wait_for(self.sreader.read(size), timeout)
            else:
                return await asyncio.wait_for(self.sreader.readline(), timeout)
        except asyncio.TimeoutError:
            return

    async def aputc(self, data, timeout=1):
        try:
            await asyncio.wait_for(self.swriter.awrite(data), timeout)
        except asyncio.TimeoutError:
            return 0
        return len(data)

    async def call(self):
        self.reply_timeout = self.call_timeout  # Takes in account the real call timeout.
        log(self.__qualname__, 'dialing...')
        for at in self.call_ats:
            if await self.cmd(at):
                if self.data.startswith('CONNECT'):
                    self.sreader.read(1)  # Clears last byte \n
                    return True
            await asyncio.sleep(self.at_delay)
        return False

    async def hangup(self):
        self.reply_timeout = self.at_timeout
        log(self.__qualname__, 'hangup...')
        for at in self.hangup_ats:
            if await self.cmd(at):
                if self.data.startswith('OK'):
                    await asyncio.sleep(self.at_delay)
                    continue
            log(self.__qualname__, 'hangup failed')
            return False
        return True

    async def data_transfer(self):
        async with self.semaphore:
            self.init_uart()
            if not files_to_send():
                log(self.__qualname__, 'nothing to send')
            elif cfg.DEBUG:
                await self.swriter.awrite('CONNECT\r')
                await asyncio.sleep(self.ymodem_delay)
                await self.send(files_to_send())
            else:
                for _ in range(self.call_attempt):
                    if await self.call():
                        await asyncio.sleep(self.ymodem_delay)  # DEBUG
                        await self.send(files_to_send())
                        #await self.recv(10)  TODO
                        await asyncio.sleep(self.keep_alive)
                        await self.hangup()
                        self.off()
                        await asyncio.sleep(2)
                        self.on()
                        return
                    await asyncio.sleep(self.at_delay)
                self.off()
                await asyncio.sleep(2)
                self.on()

    async def sms(self, text):
        self.reply_timeout = self.at_timeout
        async with self.semaphore:
            log(self.__qualname__,'sending sms...')
            self.init_uart()
            for at in self.sms_ats:
                if not await self.cmd(at):
                    log(self.__qualname__,'sms failed', at)
                    return False
                await asyncio.sleep(self.at_delay)
            await self.swriter.awrite(self.sms_to)
            try:
                self.data = await asyncio.wait_for(self.sreader.readline(), self.reply_timeout)
            except asyncio.TimeoutError:
                log(self.__qualname__,'sms failed', self.sms_to)
                return False
            if self.data.startswith(self.sms_to):
                verbose(self.data)
                try:
                    self.data = await asyncio.wait_for(self.sreader.read(2), self.reply_timeout)
                except asyncio.TimeoutError:
                    log(self.__qualname__,'sms failed')
                    return False
                if self.data.startswith('>'):
                    verbose(self.data)
                    await self.swriter.awrite(text+'\r')
                    try:
                        self.data = await asyncio.wait_for(self.sreader.readline(), 60)
                    except asyncio.TimeoutError:
                        log(self.__qualname__,'sms failed')
                        return False
                    if self.data.startswith(text):
                        verbose(self.data)
                        if await self.cmd('\x1a'):
                            return True
            log(self.__qualname__,'sms failed')
            return False
