import uasyncio as asyncio
import pyb
import time
from math import sin, cos, sqrt, atan2, radians
import tools.utils as utils
from configs import dfl, cfg
from device import DEVICE

class GPS(DEVICE):

    def __init__(self):
        DEVICE.__init__(self)
        self.sreader = asyncio.StreamReader(self.uart)
        self.swriter = asyncio.StreamWriter(self.uart, {})
        self.data = b''
        self.warmup_interval = self.config['Warmup_Interval']
        self.fix = None
        self.displacement = 0

    async def start_up(self, **kwargs):
        self.off()
        if kwargs and  'time_sync' in kwargs:
            self.time_sync = kwargs['time_sync']
        if kwargs and 'sema' in kwargs:
            self.sema = kwargs['sema']
        for _ in range(2):
            await self.main(None, tasks=['sync_rtc'])
            if self.time_sync.is_set():
                return
            await asyncio.sleep(2)
        self.time_sync.set()  # Skips time synchronization.

    def is_fixed(self):
        if not self.data.split(',')[2] == 'A':
            utils.log(self.__qualname__, 'no fix')
            return False
        return True

    def last_fix(self):
        if self.fix:
            self.calc_displacement()
        self.fix = self.data
        utils.log(self.__qualname__, 'fix acquired')

    def calc_displacement(self):
        R = 6373.0 / 1.852  # Approximate radius of earth in nm.
        fix = self.fix.split(',')
        last = self.data.split(',')
        prev_lat = radians(int(fix[3][0:2]) + float(fix[3][2:]) / 60)
        prev_lon = radians(int(fix[5][0:2]) + float(fix[5][2:]) / 60)
        last_lat = radians(int(last[3][0:2]) + float(last[3][2:]) / 60)
        last_lon = radians(int(last[5][0:2]) + float(last[5][2:]) / 60)
        a = sin((last_lat - prev_lat) / 2)**2 + cos(prev_lat) * cos(last_lat) * sin((last_lon - prev_lon) / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        self.displacement =  R * c
        if self.displacement > cfg.DISPLACEMENT_THRESHOLD:
            fix = self.data.split(',')
            utils.sms("{}-{}-{} {}:{}:{}UTC !ALERT-{}! pos {}{}'{} {}{}'{}, cog {}, sog {}kn, {:.3f}nm away from prev. pos. next msg in 5'".format(
            int(fix[9][-2:])+2000,
            fix[9][2:4],
            fix[9][0:2],
            fix[1][0:2],
            fix[1][2:4],
            fix[1][4:6],
            cfg.HOSTNAME,
            fix[3][0:2],
            fix[3][2:],
            fix[4],
            fix[5][0:3],
            fix[5][3:],
            fix[6],
            fix[8],
            fix[7],
            self.displacement))

    def sync_rtc(self):
        utc_time = self.data.split(',')[1]
        utc_date = self.data.split(',')[9]
        rtc = pyb.RTC()
        try:
            rtc.datetime((int('20'+utc_date[4:6]), int(utc_date[2:4]), int(utc_date[0:2]), 0, int(utc_time[0:2]), int(utc_time[2:4]), int(utc_time[4:6]), float(utc_time[6:])))  # rtc.datetime(yyyy, mm, dd, 0, hh, ii, ss, sss)
            utils.log(self.__qualname__, 'rtc synchronized')
        except Exception as err:
            utils.log(self.__qualname__, 'sync_rtc', type(err).__name__, err, type='e')

    def log(self):
        utils.log_data(self.data)

    async def verify_checksum(self):
        calculated_checksum = 0
        for char in self.data[1:-5]:
            calculated_checksum ^= ord(char)
            await asyncio.sleep(0)
        if '{:02X}'.format(calculated_checksum) != self.data[-4:-2]:
            utils.log(self.__qualname__, 'NMEA invalid checksum calculated: {:02X} got: {}'.format(calculated_checksum, self.data[-4:-2]))
            return False
        return True

    def decoded(self):
        try:
            self.data = self.data.decode('utf-8')
            return True
        except UnicodeError:
            utils.log(self.__qualname__, 'communication error')
            return False

    async def main(self, lock, tasks=[]):
        async with self.sema:
            self.on()
            self.init_uart()
            self.time_sync.clear()
            t0 = time.time()
            while time.time() - t0 < self.warmup_interval + self.timeout:
                try:
                    self.data = await asyncio.wait_for(self.sreader.readline(), 5)
                except asyncio.TimeoutError:
                    self.data = b''
                    utils.log(self.__qualname__, 'no data received', type='e')  # DEBUG
                    break
                if self.decoded():
                    if self.data.startswith('$') and self.data.endswith('\r\n'):
                        if await self.verify_checksum():
                            if self.data[3:6] == 'RMC':
                                rmc = self.data
                                if self.is_fixed():
                                    if 'last_fix' in tasks:
                                        self.last_fix()
                                    if 'sync_rtc' in tasks:
                                        self.sync_rtc()
                                    self.time_sync.set()
                                    break
                await asyncio.sleep(0)
            if 'log' in tasks:
                if self.data:
                    self.data = rmc[:-2]
                    async with lock:
                        self.log()
            self.uart.deinit()
            self.off()
