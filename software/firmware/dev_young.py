# dev_young.py
# MIT license; Copyright (c) 2020 Andrea Corbo

import uasyncio as asyncio
import time
import pyb
from math import sin, cos, radians, atan2, degrees, pow, sqrt, pi
from tools.utils import log, log_data, unix_epoch, iso8601
from tools.itertools import islice
from device import DEVICE

class METEO(DEVICE):

    def __init__(self):
        DEVICE.__init__(self)
        self.sreader = asyncio.StreamReader(self.uart)
        self.swriter = asyncio.StreamWriter(self.uart, {})
        self.data = b''
        self.warmup_interval = self.config['Warmup_Interval']
        self.data_length = self.config['Data_Length']
        self.string_label = self.config['String_Label']
        self.records = 0

    async def startup(self, **kwargs):
        self.on()
        self.init_uart()
        if await self.is_ready():
            log(self.__qualname__, 'successfully initialised')
        self.uart.deinit()
        self.off()

    def decode(self, data):
        try:
            data.decode('utf-8')
            return True
        except UnicodeError:
            # log(self.__qualname__, 'communication error') obviously useless!!!
            return False

    async def is_ready(self):
        try:
            line = await asyncio.wait_for(self.sreader.readline(), 10)
        except asyncio.TimeoutError:
            log(self.__qualname__, 'no answer')
            return False
        if self.decode(line):
            return True
        return False

    def wd_vect_avg(self):
        avg = 0
        def samples():
            i=0
            while i < len(self.data):
                yield [int(self.data[0+i:4+i]) * float(self.config['Meteo']['Windspeed_' + self.config['Meteo']['Windspeed_Unit']]), int(self.data[5+i:9+i])/10]
                i += self.data_length
        try:
            x = 0
            y = 0
            for sample in samples():
                direction = sample[1]
                speed = sample[0]
                x = x + (sin(radians(direction)) * speed)
                y = y + (cos(radians(direction)) * speed)
            x = x / self.records
            y = y / self.records
            avg = degrees(atan2(x, y))
            if avg < 0:
                avg += 360
        except Exception as err:
            log(self.__qualname__,'wd_vect_avg ({}): {}'.format(type(err).__name__, err), type='e')
        return avg

    def ws_vect_avg(self):
        avg = 0
        def samples():
            i=0
            while i < len(self.data):
                yield [int(self.data[0+i:4+i]) * float(self.config['Meteo']['Windspeed_' + self.config['Meteo']['Windspeed_Unit']]), int(self.data[5+i:9+i])/10]
                i += self.data_length
        try:
            x = 0
            y = 0
            for sample in samples():
                direction = sample[1]
                speed = sample[0]
                x = x + sin(radians(direction)) * speed
                y = y + cos(radians(direction)) * speed
            x = x / self.records
            y = y / self.records
            avg = sqrt(pow(x,2)+pow(y,2))
        except Exception as err:
            log(self.__qualname__,'ws_vect_avg ({}): {}'.format(type(err).__name__, err))
        return avg

    def ws_avg(self):
        avg = 0
        def samples():
            i=0
            while i < len(self.data):
                yield int(self.data[0+i:4+i]) * float(self.config['Meteo']['Windspeed_' + self.config['Meteo']['Windspeed_Unit']])
                i += self.data_length
        try:
            avg = sum(samples()) / self.records
        except Exception as err:
            log(self.__qualname__,'ws_avg ({}): {}'.format(type(err).__name__, err))
        return avg

    def gust(self):
        # Gust speed and direction.
        maxspeed = 0
        maxdir = 0

        def ws_samples():
            i=0
            while i < len(self.data):
                yield int(self.data[0+i:4+i]) * float(self.config['Meteo']['Windspeed_' + self.config['Meteo']['Windspeed_Unit']])
                i += self.data_length

        def samples():
            i=0
            while i < len(self.data):
                yield [int(self.data[0+i:4+i]) * float(self.config['Meteo']['Windspeed_' + self.config['Meteo']['Windspeed_Unit']]), int(self.data[5+i:9+i])/10]
                i += self.data_length
        try:
            glist = list()
            j = int(self.config['Meteo']['Gust_Duration'] * self.config['Sample_Rate'])
            i = 0
            s = 0
            for sample in ws_samples():
                s = s + sample
                i += 1
                if i == j:
                    glist.append(s / j)
                    i = 0
                    s = 0
            maxspeed = max(glist)
            gstart = glist.index(maxspeed) * j
            x = 0
            y = 0
            for sample in islice(samples(), gstart, gstart+j, 1):
                direction = sample[1]
                speed = sample[0]
                x = x + (sin(radians(direction)) * speed)
                y = y + (cos(radians(direction)) * speed)
            x = x / j
            y = y / j
            avg = degrees(atan2(x, y))
            if avg < 0:
                avg += 360
            maxdir = avg
        except Exception as err:
            log(self.__qualname__,'ws_max ({}): {}'.format(type(err).__name__, err))
        return maxspeed, maxdir

    def temp_avg(self):
        avg = 0
        def samples():
            i=0
            while i < len(self.data):
                yield int(self.data[10+i:14+i]) * float(self.config['Meteo']['Temp_Conv_0']) - float(self.config['Meteo']['Temp_Conv_1'])
                i += self.data_length
        try:
            avg = sum(samples()) / self.records
        except Exception as err:
            log(self.__qualname__,'temp_avg ({}): {}'.format(type(err).__name__, err))
        return avg

    def press_avg(self):
        avg = 0
        def samples():
            i=0
            while i < len(self.data):
                yield int(self.data[15+i:19+i]) * float(self.config['Meteo']['Press_Conv_0']) + float(self.config['Meteo']['Press_Conv_1'])
                i += self.data_length
        try:
            avg = sum(samples()) / self.records
        except Exception as err:
            log(self.__qualname__,'press_avg ({}): {}'.format(type(err).__name__, err))
        return avg

    def hum_avg(self):
        avg = 0
        def samples():
            i=0
            while i < len(self.data):
                yield int(self.data[20+i:24+i]) * float(self.config['Meteo']['Hum_Conv_0'])
                i += self.data_length
        try:
            avg = sum(samples()) / self.records
        except Exception as err:
            log(self.__qualname__,'hum ({}): {}'.format(type(err).__name__, err))
        return avg

    def compass_avg(self):
        avg = 0
        def samples():
            i=0
            while i < len(self.data):
                yield int(self.data[30+i:34+i]) / 10
                i += self.data_length
        try:
            x = 0
            y = 0
            for sample in samples():
                x = x + sin(radians(sample))
                y = y + cos(radians(sample))
            avg = degrees(atan2(x, y))
            if avg < 0:
                avg += 360
        except Exception as err:
            log(self.__qualname__,'compass_avg ({}): {}'.format(type(err).__name__, err))
        return avg

    def radiance_avg(self):
        avg = 0
        def samples():
            i=0
            while i < len(self.data):
                yield int(self.data[25+i:29+i]) * float(self.config['Meteo']['Rad_Conv_0'])
                i += self.data_length
        try:
            avg = sum(samples()) / self.records
        except Exception as err:
            log(self.__qualname__,'radiance_avg ({}): {}'.format(type(err).__name__, err))
        return avg

    async def log(self):
        self.ts = time.time()
        await log_data(
            '{},{},{},{:.2f},{:.2f},{:.2f},{:.2f},{:.2f},{:.2f},{:.2f},{:.2f},{:.2f},{:0d},{:.2f}'.format(
                self.string_label,
                str(unix_epoch(self.ts)),
                iso8601(self.ts),  # yyyy-mm-ddThh:mm:ssZ (controller)
                self.wd_vect_avg(),  # vect avg wind direction
                self.ws_avg(),  # avg wind speed
                self.temp_avg(),  # avg temp
                self.press_avg(),  # avg pressure
                self.hum_avg(),  # avg relative humidity
                self.compass_avg(),  # avg heading
                self.ws_vect_avg(),  # vectorial avg wind speed
                self.gust()[0], # gust speed
                self.gust()[1], # gust direction
                self.records,  # number of records
                self.radiance_avg()  # solar radiance (optional)
                )
            )

    async def main(self):
        self.on()
        self.init_uart()
        await asyncio.sleep(self.warmup_interval)
        pyb.LED(3).on()
        self.data = b''
        t0 = time.time()
        while not self._timeout(t0, self.timeout):
            try:
                line = await asyncio.wait_for(self.sreader.readline(), self.timeout)
            except asyncio.TimeoutError:
                log(self.__qualname__, 'no data received', type='e')
                break
            if not self.decode(line):
                await asyncio.sleep(0)
                continue
            if len(line) == self.data_length:
                self.data += line
            if len(self.data) == self.samples * self.data_length:
                break
            await asyncio.sleep(0)
        self.records = len(self.data) // self.data_length
        if self.data:
            await self.log()
        pyb.LED(3).off()
        self.uart.deinit()
        self.off()

    async def manual(self):
        self.on()
        self.init_uart()
        await asyncio.sleep(self.warmup_interval)
        pyb.LED(3).on()
        while True:
            self.data = b''
            t0 = time.time()
            while not self._timeout(t0, self.timeout):
                try:
                    line = await asyncio.wait_for(self.sreader.readline(), self.timeout)
                except asyncio.TimeoutError:
                    log(self.__qualname__, 'no data received', type='e')
                    break
                if not self.decode(line):
                    await asyncio.sleep(0)
                    continue
                if len(line) == self.data_length:
                    self.data += line
                if len(self.data) == self.samples * self.data_length:
                    break
                await asyncio.sleep(0)
            self.records = len(self.data) // self.data_length
            if self.data:
                await self.log()
        pyb.LED(3).off()
        self.uart.deinit()
        self.off()
