import uasyncio as asyncio
import pyb
import time
from math import sin, cos, radians, atan2, degrees, pow, sqrt
import tools.utils as utils
from configs import dfl, cfg
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

    async def start_up(self, **kwargs):
        if kwargs and 'sema' in kwargs:
            self.sema = kwargs['sema']
        async with self.sema:
            self.on()
            self.init_uart()
            if await self.is_ready():
                utils.log(self.__qualname__, 'successfully initialised')
            self.uart.deinit()
            self.off()

    def decode(self, data):
        try:
            data.decode('utf-8')
            return True
        except UnicodeError:
            utils.log(self.__qualname__, 'communication error')
            return False

    async def is_ready(self):
        try:
            line = await asyncio.wait_for(self.sreader.readline(), 10)
        except asyncio.TimeoutError:
            utils.log(self.__qualname__, 'no answer')
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
            avg = degrees(atan2(x, y))
            if avg < 0:
                avg += 360
        except Exception as err:
            utils.log(self.__qualname__,'wd_vect_avg ({}): {}'.format(type(err).__name__, err), type='e')
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
                x = x + (sin(radians(direction)) * pow(speed,2))
                y = y + (cos(radians(direction)) * pow(speed,2))
            avg = sqrt(x+y) / self.records
        except Exception as err:
            utils.log(self.__qualname__,'ws_vect_avg ({}): {}'.format(type(err).__name__, err))
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
            utils.log(self.__qualname__,'ws_avg ({}): {}'.format(type(err).__name__, err))
        return avg

    def ws_max(self):
        # Gust speed.
        maxspeed = 0
        def samples():
            i=0
            while i < len(self.data):
                yield int(self.data[0+i:4+i]) * float(self.config['Meteo']['Windspeed_' + self.config['Meteo']['Windspeed_Unit']])
                i += self.data_length
        try:
            maxspeed = max(samples())
        except Exception as err:
            utils.log(self.__qualname__,'ws_max ({}): {}'.format(type(err).__name__, err))
        return maxspeed

    def wd_max(self):
        # Gust direction.
        maxdir = 0
        def samples():
            i=0
            while i < len(self.data):
                yield [int(self.data[0+i:4+i]) * float(self.config['Meteo']['Windspeed_' + self.config['Meteo']['Windspeed_Unit']]), int(self.data[5+i:9+i])/10]
                i += self.data_length
        try:
            for sample in samples():
                if sample[0] == self.ws_max():
                    maxdir = sample[1] / 10
        except Exception as err:
            utils.log(self.__qualname__,'wd_max ({}): {}'.format(type(err).__name__, err))
        return maxdir

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
            utils.log(self.__qualname__,'temp_avg ({}): {}'.format(type(err).__name__, err))
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
            utils.log(self.__qualname__,'press_avg ({}): {}'.format(type(err).__name__, err))
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
            utils.log(self.__qualname__,'hum ({}): {}'.format(type(err).__name__, err))
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
            utils.log(self.__qualname__,'compass_avg ({}): {}'.format(type(err).__name__, err))
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
            utils.log(self.__qualname__,'radiance_avg ({}): {}'.format(type(err).__name__, err))
        return avg

    def log(self):
        self.ts = time.time()
        utils.log_data(
            '{},{},{},{},{:.1f},{:.1f},{:.1f},{:.1f},{:.1f},{:.1f},{:.1f},{:.1f},{:.1f},{:0d},{:.1f}'.format(
                self.string_label,
                str(utils.unix_epoch(self.ts)),
                utils.iso8601(self.ts),  # yyyy-mm-ddThh:mm:ssZ (controller)
                self.wd_vect_avg(),  # vectorial avg wind direction
                self.ws_avg(),  # avg wind speed
                self.temp_avg(),  # avg temp
                self.press_avg(),  # avg pressure
                self.hum_avg(),  # avg relative humidity
                self.compass_avg(),  # avg heading
                self.ws_vect_avg(),  # vectorial avg wind speed
                self.ws_max(),  # gust speed
                self.wd_max(),  # gust direction
                self.records,  # number of records
                self.radiance_avg()  # solar radiance (optional)
                )
            )

    async def main(self, lock, tasks=[]):
        async with self.sema:
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
                    utils.log(self.__qualname__, 'no data received', type='e')
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
                async with lock:
                    self.log()
            pyb.LED(3).off()
            self.uart.deinit()
            self.off()
