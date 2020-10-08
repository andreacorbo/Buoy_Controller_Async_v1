import uasyncio as asyncio
import pyb
import time
from math import sin, cos, sqrt, atan2, radians
from tools.utils import log, log_data, timesync, uart2_sema, set_sms
from configs import cfg
from device import DEVICE

class GPS(DEVICE):

    def __init__(self):
        DEVICE.__init__(self)
        self.sreader = asyncio.StreamReader(self.uart)
        self.swriter = asyncio.StreamWriter(self.uart, {})
        self.data = b''
        self.semaphore = uart2_sema
        self.warmup_interval = self.config['Warmup_Interval']
        self.fix = None
        self.fixed = timesync
        self.displacement = 0

    async def start_up(self, **kwargs):
        async with self.semaphore:
            self.on()
        for _ in range(2):
            await self.main(['sync_rtc'])
            if self.fixed.is_set():
                return
            await asyncio.sleep(2)
        self.fixed.set()  # Skips time synchronization.

    def is_fixed(self):
        if not self.data.split(',')[2] == 'A':
            log(self.__qualname__, 'no fix')
            return False
        self.fixed.set()
        return True

    def last_fix(self):
        if self.fix:
            self.calc_displacement()
        self.fix = self.data
        log(self.__qualname__, 'fix acquired')

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
        if self.displacement > cfg.DISPLACEMENT_THRESHOLD and float(last[7]) > 0:
            set_sms('{}-{}-{}T{}:{}:{}Z ***ALERT*** {} is {:.3f}nm ({}m) away from prev. pos. (coord {}{}\'{} {}{}\'{}, cog {}, sog {}kn) next msg in 5\''.format(
            int(last[9][-2:])+2000,
            last[9][2:4],
            last[9][0:2],
            last[1][0:2],
            last[1][2:4],
            last[1][4:6],
            cfg.HOSTNAME,
            self.displacement,
            int(self.displacement*1852),
            last[3][0:2],
            last[3][2:],
            last[4],
            last[5][0:3],
            last[5][3:],
            last[6],
            last[8],
            last[7]))

    def sync_rtc(self):
        utc_time = self.data.split(',')[1]
        utc_date = self.data.split(',')[9]
        rtc = pyb.RTC()
        try:
            rtc.datetime((int('20'+utc_date[4:6]), int(utc_date[2:4]), int(utc_date[0:2]), 0, int(utc_time[0:2]), int(utc_time[2:4]), int(utc_time[4:6]), float(utc_time[6:])))  # rtc.datetime(yyyy, mm, dd, 0, hh, ii, ss, sss)
            log(self.__qualname__, 'rtc synchronized')
        except Exception as err:
            log(self.__qualname__, 'sync_rtc', type(err).__name__, err, type='e')

    async def log(self):
        await log_data(self.data)

    async def verify_checksum(self):
        calculated_checksum = 0
        for char in self.data[1:-5]:
            calculated_checksum ^= ord(char)
            await asyncio.sleep(0)
        if '{:02X}'.format(calculated_checksum) != self.data[-4:-2]:
            log(self.__qualname__, 'NMEA invalid checksum calculated: {:02X} got: {}'.format(calculated_checksum, self.data[-4:-2]))
            return False
        return True

    def decoded(self):
        try:
            self.data = self.data.decode('utf-8')
            return True
        except UnicodeError:
            log(self.__qualname__, 'communication error', self.data)
            return False

    async def main(self, tasks=[]):
        async with self.semaphore:
            #self.on()
            self.init_uart()
            await asyncio.sleep(1)
            self.fixed.clear()
            t0 = time.time()
            while time.time() - t0 < self.warmup_interval + self.timeout:
                try:
                    self.data = await asyncio.wait_for(self.sreader.readline(), 2)
                except asyncio.TimeoutError:
                    self.data = b''
                    log(self.__qualname__, 'no data received', type='e')
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
                                    break
                await asyncio.sleep(0)
            if 'log' in tasks and rmc:
                self.data = rmc[:-2]
                await self.log()
            self.uart.deinit()  # Releases the uart to the meteo.
            self.off()  # Switches off itself to avoid conflicts with the meteo.
        await asyncio.sleep(1)
        async with self.semaphore:
            self.on()  # Powers on itself again as soon as the meteo task ends.
