# dev_gps.py
# MIT license; Copyright (c) 2020 Andrea Corbo

import uasyncio as asyncio
import time
import pyb
from math import sin, cos, sqrt, atan2, radians
from tools.utils import log, log_data, timesync, set_alert, verbose
from configs import cfg
from device import DEVICE

class GPS(DEVICE):

    def __init__(self):
        DEVICE.__init__(self)
        self.sreader = asyncio.StreamReader(self.uart)
        self.swriter = asyncio.StreamWriter(self.uart, {})
        self.data = b''
        self.warmup_interval = self.config['Warmup_Interval']
        self.fix = None
        self.fixed = timesync
        self.displacement = 0

    async def startup(self, **kwargs):
        await self.main('sync_rtc')
        if not self.fixed.is_set():
            self.fixed.set()  # Skips time synchronization.

    def is_fixed(self):
        if self.data.split(',')[2] == 'A':
            self.fixed.set()
            return True
        log(self.__qualname__, 'no fix')
        return False

    def last_fix(self):
        if self.fix:
            self.calc_displacement()
        self.fix = self.data
        log(self.__qualname__, 'fix acquired')

    def calc_displacement(self):
        R = 6373.0 / 1.852  # Approximate radius of earth in nm.
        prev = self.fix.split(',')
        last = self.data.split(',')
        p_lat = radians(int(prev[3][0:2]) + float(prev[3][2:]) / 60)
        p_lon = radians(int(prev[5][0:2]) + float(prev[5][2:]) / 60)
        l_lat = radians(int(last[3][0:2]) + float(last[3][2:]) / 60)
        l_lon = radians(int(last[5][0:2]) + float(last[5][2:]) / 60)
        a = sin((l_lat - p_lat) / 2)**2 + cos(p_lat) * cos(l_lat) * sin((l_lon - p_lon) / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        self.displacement =  R * c
        if self.displacement > cfg.DISPLACEMENT_THRESHOLD and float(last[7]) > 0:
            set_alert('{}-{}-{}T{}:{}:{}Z ***ALERT*** {} is {:.3f}nm ({}m) away from prev. pos. (coord {}{}\'{} {}{}\'{}, cog {}, sog {}kn) next msg in 5\''.format(
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
        tm = self.data.split(',')[1]
        dt = self.data.split(',')[9]
        rtc = pyb.RTC()
        try:
            rtc.calibration(cfg.RTC_CALIBRATION)
            log(self.__qualname__, 'rtc calibration factor', cfg.RTC_CALIBRATION)
        except Exception as err:
            log(self.__qualname__, 'sync_rtc', type(err).__name__, err, type='e')
        try:
            rtc.datetime((
                int('20'+dt[4:6]),  # yyyy
                int(dt[2:4]),       # mm
                int(dt[0:2]),       # dd
                0,                  # 0
                int(tm[0:2]),       # hh
                int(tm[2:4]),       # mm
                int(tm[4:6]),       # ss
                float(tm[6:])))     # sss
            log(self.__qualname__, 'rtc synchronized')
        except Exception as err:
            log(self.__qualname__, 'sync_rtc', type(err).__name__, err, type='e')

    async def log(self):
        await log_data(self.data)

    async def verify_checksum(self):
        cksum = 0
        for c in self.data[1:-5]:
            cksum ^= ord(c)
            await asyncio.sleep(0)
        if '{:02X}'.format(cksum) == self.data[-4:-2]:
            return True
        log(self.__qualname__, 'NMEA invalid checksum calculated: {:02X} got: {}, {}'.format(cksum, self.data[-4:-2], self.data))
        return False

    def decoded(self):
        try:
            self.data = self.data.decode('utf-8')
            return True
        except UnicodeError:
            # log(self.__qualname__, 'communication error') obviously useless!!!
            return False

    async def main(self, task='log'):
        if isinstance(task,str):
            t=[]
            t.append(task)
        else:
            t = task
        self.on()
        self.init_uart()
        self.fixed.clear()
        rmc = ''
        t0 = time.time()
        while time.time() - t0 < self.warmup_interval:
            try:
                self.data = await asyncio.wait_for(self.sreader.readline(), self.warmup_interval)
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
                                if 'last_fix' in t:
                                    self.last_fix()
                                if 'sync_rtc' in t:
                                    self.sync_rtc()
                                break
            await asyncio.sleep(0)
        if 'log' in t and rmc:
            self.data = rmc[:-2]
            await self.log()
        self.uart.deinit()
        self.off()
