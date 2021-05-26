# device.py
# MIT license; Copyright (c) 2020 Andrea Corbo

import time
import pyb
from tools.utils import log, read_cfg
from configs import dfl, cfg

class DEVICE:

    def __init__(self):
        self.name = self.__module__ + '.' + self.__qualname__
        self.get_config()
        self.samples = 0
        if 'Samples' in self.config:
            self.samples = self.config['Samples']
        self.sample_rate = 0
        if 'Sample_Rate' in self.config:
            self.sample_rate = self.config['Sample_Rate']
        self.timeout = 0
        if self.sample_rate > 0:
            self.timeout = self.samples // self.sample_rate + (self.samples % self.sample_rate > 0) + cfg.TIMEOUT
        self.set_uart()
        self.init_gpio()
        try:
            self.off()
        except:
            pass  # Devices without gpio.

    def _timeout(self, start, expire=0):
        if not expire:
            expire = cfg.TIMEOUT
        if expire > 0 and time.time() - start >= expire:
            log(self.__qualname__, 'timeout occurred', type='e')
            return True
        return False

    def get_config(self):
        try:
            self.config = read_cfg(self.__module__)[self.__qualname__]
            return self.config
        except Exception as err:
            log(self.__qualname__, type(err).__name__, err, type='e')

    def set_uart(self):
        if 'Uart' in self.config:
            self.uart_bus = dfl.UARTS[dfl.DEVS.index(self.name)] if self.name in dfl.DEVS else dfl.UARTS[cfg.DEVS.index(self.name)]
            try:
                self.uart = pyb.UART(self.uart_bus, int(self.config['Uart']['Baudrate']))
            except Exception as err:
                log(self.__qualname__, type(err).__name__, err, type='e')

    def init_uart(self):
        if self.uart:
            try:
                self.uart.init(int(self.config['Uart']['Baudrate']),
                    bits=int(self.config['Uart']['Bits']),
                    parity=eval(self.config['Uart']['Parity']),
                    stop=int(self.config['Uart']['Stop']),
                    timeout=int(self.config['Uart']['Timeout']),
                    flow=int(self.config['Uart']['Flow_Control']),
                    timeout_char=int(self.config['Uart']['Timeout_Char']),
                    read_buf_len=int(self.config['Uart']['Read_Buf_Len']))
            except Exception as err:
                log(self.__qualname__, type(err).__name__, err, type='e')

    def init_gpio(self):
        try:
            self.gpio = pyb.Pin(dfl.CTRL_PINS[dfl.DEVS.index(self.name) if self.name in dfl.DEVS else cfg.DEVS.index(self.name)], pyb.Pin.OUT, pyb.Pin.PULL_DOWN)
        except IndexError:
            pass  # device has no gpio
        except Exception as err:
            log(self.__qualname__, type(err).__name__, err, type='e')

    def on(self):
        if hasattr(self, 'gpio'):
            self.gpio.on()  # set pin to off
        log(self.__qualname__,dfl.STATUS[self.gpio.value()])

    def off(self):
        if hasattr(self, 'gpio'):
            self.gpio.off()  # set pin to off
        log(self.__qualname__,dfl.STATUS[self.gpio.value()])

    def toggle(self):
        if hasattr(self, 'gpio'):
            if self.gpio.value() > 0:
                self.gpio.off()
            else:
                self.gpio.on()
