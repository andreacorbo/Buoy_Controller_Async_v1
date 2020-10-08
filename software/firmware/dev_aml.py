import uasyncio as asyncio
import pyb
import time
from tools.utils import log, log_data, unix_epoch, iso8601, timesync
from configs import dfl
from device import DEVICE

ENTER = '\r'
PROMPT = '>'

class CTD(DEVICE):

    def __init__(self):
        DEVICE.__init__(self)
        self.sreader = asyncio.StreamReader(self.uart)
        self.swriter = asyncio.StreamWriter(self.uart, {})
        self.data = b''
        self.prompt_timeout = self.config['Ctd']['Prompt_Timeout']
        self.warmup_interval = self.config['Warmup_Interval']

    async def start_up(self, **kwargs):
        self.on()
        self.init_uart()
        await asyncio.sleep(1)  # Waits for uart getting ready.
        if await self.brk():
            await self.set('STARTUP NOHEADER')
            await self.set('STARTUP MONITOR')
            await self.set_sample_rate()
            await self.set('SCAN TIME')
            await self.set('SCAN DATE')
            await self.set('SCAN DENSITY')
            await self.set('SCAN SALINITY')
            await self.set('SCAN SV')
            await self.zero()
            await timesync.wait()
            await self.set_clock()
            await self.set_log()
            await self.set('SCAN LOGGING')
            log(self.__qualname__, 'successfully initialised')
        self.uart.deinit()
        self.off()

    def decoded(self):
        #
        # Decodes chars in order to check wether a connection issue has occurred.
        #
        try:
            self.data = self.data.decode('utf-8')
            return True
        except UnicodeError:
            log(self.__qualname__, 'communication error')
            return False

    async def brk(self):
        #
        # Sends a break.
        #
        while True:
            await self.swriter.awrite(ENTER)
            try:
                self.data = await asyncio.wait_for(self.sreader.read(128), self.prompt_timeout)
            except:
                log(self.__qualname__, 'no answer')
                return False
            if self.decoded():
                if self.data.endswith(PROMPT):
                    return True
            await asyncio.sleep_ms(500)  # TODO: check if 1s is enough
        return False

    async def set(self, cmd):
        #
        # Set commands.
        #
        await self.swriter.awrite('SET ' + cmd + ENTER)
        if await self.reply():
            if self.data.startswith(cmd,4):  # Ignores 'SET '.
                await self.sreader.read(1)  # Flushes '>'.
                return True
        return False

    async def dis(self,cmd):
        #
        # Display commands.
        #
        await self.swriter.awrite('DIS ' + cmd + ENTER)
        if await self.reply():
            if self.data.startswith(cmd,4):  # Ignores 'SET '.
                if await self.reply():
                    self.data = self.data[:-2]  # Removes '\r\n'.
                    await self.sreader.read(1)  # Flushes '>'.
                    return True
        return False

    async def reply(self):
        #
        # Captures commands replies.
        #
        try:
            self.data = await asyncio.wait_for(self.sreader.readline(), self.timeout)
        except asyncio.TimeoutError:
            log(self.__qualname__, 'no answer')
            return False
        if self.decoded():
            return True
        return False

    async def set_clock(self):
        date = None
        time = None
        if await self.brk():
            if await self.set_time() and await self.set_date():
                if await self.dis('DATE'):
                    date = self.data[-10:]
                if await self.dis('TIME'):
                    time = self.data[-11:]
                log(self.__qualname__,'instrument clock synchronized {}T{}Z'.format(date, time))
                return
        log(self.__qualname__, 'unable to synchronize the instrument clock', type='e')

    async def set_date(self):
        CMD = 'DATE'
        now = time.localtime()
        if await self.set(CMD + ' {:02d}/{:02d}/{:02d}'.format(now[1], now[2], int(str(now[0])[2:]))):
            return True
        return False

    async def set_time(self):
        CMD = 'TIME'
        now = time.localtime()
        if await self.set(CMD + ' {:02d}:{:02d}:{:02d}'.format(now[3], now[4], now[5])):
            return True
        return False

    async def set_sample_rate(self):
        CMD = 'S'
        if await self.set(CMD + ' {:0d} S'.format(self.sample_rate)):
            if await self.dis(CMD):
                log(self.__qualname__, self.data)
        else:
            log(self.__qualname__, 'unable to set the sample rate', type='e')

    async def set_log(self):
        CMD = 'LOG'
        now = time.localtime()
        if await self.set(CMD + ' {:04d}{:02d}{:02d}.txt'.format(now[0], now[1], now[2])):
            if await self.dis(CMD):
                log(self.__qualname__, self.data)
        else:
            log(self.__qualname__, 'unable to create log', type='e')

    async def zero(self):
        #
        # Corrects the barometric offset to set zero.
        #
        if await self.scan():  # Gets one sample.
            self.format_data()
            if float(self.data[8]) < 1:  # Checks conductivity to
                CMD = 'ZERO'                         # esablish if in air.
                await self.swriter.awrite(CMD + ENTER)
                if await self.reply():
                    if self.data.startswith(CMD):
                        if await self.reply():
                            log(self.__qualname__, self.data[:-2])
                            return
                log(self.__qualname__, 'unable to zero pressure at surface', type='e')


    def format_data(self):
        tmp = []
        for _ in self.data[:-2].split(' '):
            if _ != '':
                tmp.append(_)
        self.data = tmp

    async def scan(self):
        #
        # Gets one sample.
        #
        CMD = 'SCAN'
        await self.swriter.awrite(CMD + ENTER)
        if await self.reply():
            if self.data.startswith(CMD):
                if await self.reply():
                    await self.sreader.read(1)  # Flushes '>'.
                    return True
        return False

    async def log(self):
        self.ts = time.time()
        self.format_data()
        await log_data(
            dfl.DATA_SEPARATOR.join(
                [
                    self.config['String_Label'],
                    str(unix_epoch(self.ts)),
                    iso8601(self.ts)  # yyyy-mm-ddThh:mm:ssZ (controller)
                ]
                + self.data
            )
        )

    async def main(self, tasks=[]):
        self.on()
        self.init_uart()
        await asyncio.sleep(1)
        await self.swriter.awrite(ENTER)
        await asyncio.sleep(self.warmup_interval)
        pyb.LED(3).on()
        try:
            self.data = await asyncio.wait_for(self.sreader.readline(), 2)
        except asyncio.TimeoutError:
            self.data = b''
            log(self.__qualname__, 'no data received', type='e')  # DEBUG
        if self.data:
            if self.decoded():
                await self.log()
        pyb.LED(3).off()
        self.uart.deinit()
        self.off()

class UV(DEVICE):

    def __init__(self):
        DEVICE.__init__(self)
        self.warmup_interval = self.config['Warmup_Interval']

    async def start_up(self, **kwargs):
        await asyncio.sleep(0)

    async def main(self, *args):
        self.on()
        await asyncio.sleep(self.warmup_interval)
        self.off()
