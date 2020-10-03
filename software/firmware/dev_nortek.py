import uasyncio as asyncio
import pyb
import time
import binascii
import struct
import select
import _thread
from configs import dfl, cfg
import tools.utils as utils
from device import DEVICE

class ADCP(DEVICE):

    coord_system = {
        0:'ENU',
        1:'XYZ',
        2:'BEAM'
        }

    evt = asyncio.Event()

    def __init__(self):
        DEVICE.__init__(self)
        self.sreader = asyncio.StreamReader(self.uart)
        self.swriter = asyncio.StreamWriter(self.uart, {})
        self.data = b''
        self.break_timeout = self.config['Adcp']['Break_Timeout']
        self.instrument_config = self.config['Adcp']['Instrument_Config']
        self.deployment_config = self.config['Adcp']['Deployment_Config']
        self.deployment_delay = self.config['Adcp']['Deployment_Delay']

    async def start_up(self, **kwargs):
        self.off()
        await asyncio.sleep(1)
        self.on()
        self.init_uart()
        await asyncio.sleep(1) # Waits for uart getting ready.
        if await self.brk():
            if kwargs and 'time_sync' in kwargs:
                await kwargs['time_sync'].wait()
                await self.set_clock()
                await self.set_usr_cfg()
                await self.get_cfg()
                await self.start_delayed()
                #await self.parse_cfg()
                utils.log(self.__qualname__, 'successfully initialised')

    def decode(self):
        try:
            self.data.decode('utf-8')
            return True
        except UnicodeError:
            utils.log(self.__qualname__, 'communication error')
            return False

    async def reply(self, timeout=10):
        self.data = b''
        try:
            self.data = await asyncio.wait_for(self.sreader.read(1024), timeout)
            #utils.verbose(self.data)
        except asyncio.TimeoutError:
            utils.log(self.__qualname__, 'no answer')
            return False
        #if self.decode():  TODO: Check if it works.
        #    return True
        return True

    def ack(self):
        if self.data[-2:] == b'\x06\x06':
            return True
        elif self.data[-2:] == b'\x15\x15':
            return False

    async def brk(self):

        async def confirm():
            await self.swriter.awrite('MC')
            if await self.reply(self.break_timeout):
                if self.ack():
                    return True
            return False

        await self.swriter.awrite('@@@@@@')
        await asyncio.sleep_ms(100)
        await self.swriter.awrite('K1W%!Q')
        while await self.reply(self.break_timeout):
            if self.data.endswith(b'\x15\x15\x15'):
                await asyncio.sleep(0)
                continue
            if self.ack():
                if b'\x0a\x0d\x43\x6f\x6e\x66\x69\x72\x6d\x3a' in self.data:
                    if await confirm():
                        return True
                    else:
                        return False
                return True
        return False

    async def calc_checksum(self, data):
        # Computes the data checksum: b58c(hex) + sum of all words in the structure.
        sum=0
        j=0
        for i in range(int.from_bytes(data[2:4], 'little')-1):
            sum += int.from_bytes(data[j:j+2], 'little')
            j = j+2
            await asyncio.sleep(0)
        return (int.from_bytes(b'\xb5\x8c', 'big') + sum) % 65536

    async def verify_checksum(self, data):
        checksum = int.from_bytes(data[-2:], 'little')
        calc_checksum = await self.calc_checksum(data)
        if checksum == calc_checksum:
            return True
        utils.log(self.__qualname__, 'invalid checksum calculated: {} got: {}'.format(calc_checksum, checksum))
        return False

    async def set_clock(self):
        # Sets up the instrument RTC.
        # mm ss DD hh YY MM (3 words of 2 bytes each)
        async def get_clock():
            if await self.brk():
                await self.swriter.awrite('RC')
                if await self.reply():
                    if self.ack():
                        try:
                            self.data = binascii.hexlify(self.data)
                            return '20{:2s}-{:2s}-{:2s} {:2s}:{:2s}:{:2s}'.format(
                                self.data[8:10], # Year
                                self.data[10:12],# Month
                                self.data[4:6],  # Day
                                self.data[6:8],  # Hour
                                self.data[0:2],  # Minute
                                self.data[2:4])  # Seconds
                        except Exception as err:
                            utils.log(self.__qualname__, 'get_clock', type(err).__name__, err, type='e')
                            return False

        if await self.brk():
            now = time.localtime()
            await self.swriter.awrite('SC')
            await self.swriter.awrite(binascii.unhexlify('{:02d}{:02d}{:02d}{:02d}{:02d}{:02d}'.format(now[4], now[5], now[2], now[3], int(str(now[0])[2:]), now[1])))
            if await self.reply():
                if self.ack():
                    utils.log(self.__qualname__, 'instrument clock synchronized UTC({})'.format(await get_clock()))
                    return True
            utils.log(self.__qualname__, 'unable to synchronize the instrument clock', type='e')
            return False

    async def get_cfg(self):
        # Retreives the complete configuration from the instrument.
        flag = False
        def filewriter():
            nonlocal flag
            try:
                with open(dfl.CONFIG_DIR + self.instrument_config, 'wb') as conf:
                    conf.write(self.data)
                    flag = True
            except Exception as err:
                utils.log(self.__qualname__, 'get_cfg', type(err).__name__, err, type='e')
            self.evt.set()

        if await self.brk():
            await self.swriter.awrite('GA')
            if await self.reply():
                if self.ack() and await self.verify_checksum(self.data[0:48]) and await self.verify_checksum(self.data[48:272]) and await self.verify_checksum(self.data[272:784]):
                    _thread.start_new_thread(filewriter, ())
                    await asyncio.sleep_ms(10)
                    await self.evt.wait()
                    self.evt.clear()
                    if flag:
                        return True
        utils.log(self.__qualname__, 'unable to retreive the instrument configuration', type='e')
        return False

    async def parse_cfg(self):

        def parse_hw_cfg(bytestring):

            def decode_hw_cfg(conf):
                try:
                    return (
                        'RECORDER {}'.format('NO' if conf >> 0 & 1  else 'YES'),
                        'COMPASS {}'.format('NO' if conf >> 1 & 1  else 'YES')
                        )
                except Exception as err:
                    utils.log(self.__qualname__, 'decode_hw_cfg', type(err).__name__, err)

            def decode_hw_status(status):
                try:
                    return 'VELOCITY RANGE {}'.format('HIGH' if status >> 0 & 1  else 'NORMAL')
                except Exception as err:
                    utils.log(self.__qualname__, 'decode_hw_status', type(err).__name__, err)

            try:
                return (
                    '{:02x}'.format(bytestring[0]),                                 # [0] Sync
                    '{:02x}'.format(int.from_bytes(bytestring[1:2], 'little')),     # [1] Id
                    int.from_bytes(bytestring[2:4], 'little'),                      # [2] Size
                    bytestring[4:18].decode('ascii'),                               # [3] SerialNo
                    decode_hw_cfg(int.from_bytes(bytestring[18:20], 'little')),     # [4] Config
                    int.from_bytes(bytestring[20:22], 'little'),                    # [5] Frequency
                    bytestring[22:24],                                              # [6] PICVersion
                    int.from_bytes(bytestring[24:26], 'little'),                    # [7] HWRevision
                    int.from_bytes(bytestring[26:28], 'little'),                    # [8] RecSize
                    decode_hw_status(int.from_bytes(bytestring[28:30], 'little')),  # [9] Status
                    bytestring[30:42],                                              # [10] Spare
                    bytestring[42:46].decode('ascii')                               # [11] FWVersion
                    )
            except Exception as err:
                utils.log(self.__qualname__, 'parse_cfg__', type(err).__name__, err)

        def parse_head_cfg(bytestring):

            def decode_head_cfg(conf):
                try:
                    return (
                        'PRESSURE SENSOR {}'.format('YES' if conf >> 0 & 1  else 'NO'),
                        'MAGNETOMETER SENSOR {}'.format('YES' if conf >> 1 & 1  else 'NO'),
                        'TILT SENSOR {}'.format('YES' if conf >> 2 & 1  else 'NO'),
                        '{}'.format('DOWN' if conf >> 3 & 1  else 'UP')
                        )
                except Exception as err:
                    utils.log(self.__qualname__, 'decode_head_cfg', type(err).__name__, err)

            try:
                return (
                    '{:02x}'.format(bytestring[0]),                               # [0] Sync
                    '{:02x}'.format(int.from_bytes(bytestring[1:2], 'little')),   # [1] Id
                    int.from_bytes(bytestring[2:4], 'little') * 2,                # [2] Size
                    decode_head_cfg(int.from_bytes(bytestring[4:6], 'little')),   # [3] Config
                    int.from_bytes(bytestring[6:8], 'little'),                    # [4] Frequency
                    bytestring[8:10],                                             # [5] Type
                    bytestring[10:22].decode('ascii'),                            # [6] SerialNo
                    bytestring[22:198],                                           # [7] System
                    bytestring[198:220],                                          # [8] Spare
                    int.from_bytes(bytestring[220:222], 'little')                 # [9] NBeams
                    )
            except Exception as err:
                utils.log(self.__qualname__, 'parse_head_cfg', type(err).__name__, err)

        def parse_usr_cfg(bytestring):

            def decode_usr_timctrlreg(bytestring):
                try:
                    return '{:016b}'.format(bytestring)
                except Exception as err:
                    utils.log(self.__qualname__, 'decode_usr_timctrlreg', type(err).__name__, err)

            def decode_usr_pwrctrlreg(bytestring):
                try:
                    return '{:016b}'.format(bytestring)
                except Exception as err:
                    utils.log(self.__qualname__, 'decode_usr_pwrctrlreg', type(err).__name__, err)

            def decode_usr_mode(bytestring):
                try:
                    return '{:016b}'.format(bytestring)
                except Exception as err:
                    utils.log(self.__qualname__, 'decode_usr_mode', type(err).__name__, err)

            def decode_usr_modetest(bytestring):
                try:
                    return '{:016b}'.format(bytestring)
                except Exception as err:
                    utils.log(self.__qualname__, 'decode_usr_modetest', type(err).__name__, err)

            def decode_usr_wavemode(bytestring):
                try:
                    return '{:016b}'.format(bytestring)
                except Exception as err:
                    utils.log(self.__qualname__, 'decode_usr_wavemode', type(err).__name__, err)

            try:
                return (
                    '{:02x}'.format(bytestring[0]),                                     # [0] Sync
                    '{:02x}'.format((int.from_bytes(bytestring[1:2], 'little'))),       # [1] Id
                    int.from_bytes(bytestring[2:4], 'little'),                          # [2] Size
                    int.from_bytes(bytestring[4:6], 'little'),                          # [3] T1
                    int.from_bytes(bytestring[6:8], 'little'),                          # [4] T2, BlankingDistance
                    int.from_bytes(bytestring[8:10], 'little'),                         # [5] T3
                    int.from_bytes(bytestring[10:12], 'little'),                        # [6] T4
                    int.from_bytes(bytestring[12:14], 'little'),                        # [7] T5
                    int.from_bytes(bytestring[14:16], 'little'),                        # [8] NPings
                    int.from_bytes(bytestring[16:18], 'little'),                        # [9] AvgInterval
                    int.from_bytes(bytestring[18:20], 'little'),                        # [10] NBeams
                    decode_usr_timctrlreg(int.from_bytes(bytestring[20:22], 'little')), # [11] TimCtrlReg
                    decode_usr_pwrctrlreg(int.from_bytes(bytestring[22:24], 'little')), # [12] Pwrctrlreg
                    bytestring[24:26],                                                  # [13] A1 Not used.
                    bytestring[26:28],                                                  # [14] B0 Not used.
                    bytestring[28:30],                                                  # [15] B1 Not used.
                    int.from_bytes(bytestring[30:32], 'little'),                        # [16] CompassUpdRate
                    self.coord_system[int.from_bytes(bytestring[32:34], 'little')],     # [17] CoordSystem
                    int.from_bytes(bytestring[34:36], 'little'),                        # [18] Nbins
                    int.from_bytes(bytestring[36:38], 'little'),                        # [19] BinLength
                    int.from_bytes(bytestring[38:40], 'little'),                        # [20] MeasInterval
                    bytestring[40:46].decode('utf-8'),                                  # [21] DeployName
                    int.from_bytes(bytestring[46:48], 'little'),                        # [22] WrapMode
                    binascii.hexlify(bytestring[48:54]).decode('utf-8'),                # [23] ClockDeploy
                    int.from_bytes(bytestring[54:58], 'little'),                        # [24] DiagInterval
                    decode_usr_mode(int.from_bytes(bytestring[58:60], 'little')),       # [25] Mode
                    int.from_bytes(bytestring[60:62], 'little'),                        # [26] AdjSoundSpeed
                    int.from_bytes(bytestring[62:64], 'little'),                        # [27] NSampDiag
                    int.from_bytes(bytestring[64:66], 'little'),                        # [28] NbeamsCellDiag
                    int.from_bytes(bytestring[66:68], 'little'),                        # [29] NpingDiag
                    decode_usr_modetest(int.from_bytes(bytestring[68:70], 'little')),   # [30] ModeTest
                    int.from_bytes(bytestring[68:72], 'little'),                        # [31] AnaInAddr
                    int.from_bytes(bytestring[72:74], 'little'),                        # [32] SWVersion
                    int.from_bytes(bytestring[74:76], 'little'),                        # [33] Salinity
                    binascii.hexlify(bytestring[76:256]),                               # [34] VelAdjTable
                    bytestring[256:336].decode('utf-8'),                                # [35] Comments
                    binascii.hexlify(bytestring[336:384]),                              # [36] Spare
                    int.from_bytes(bytestring[384:386], 'little'),                      # [37] Processing Method
                    binascii.hexlify(bytestring[386:436]),                              # [38] Spare
                    decode_usr_wavemode(int.from_bytes(bytestring[436:438], 'little')), # [39] Wave Measurement Mode
                    int.from_bytes(bytestring[438:440], 'little'),                      # [40] DynPercPos
                    int.from_bytes(bytestring[440:442], 'little'),                      # [41] T1
                    int.from_bytes(bytestring[442:444], 'little'),                      # [42] T2
                    int.from_bytes(bytestring[444:446], 'little'),                      # [43] T3
                    int.from_bytes(bytestring[446:448], 'little'),                      # [44] NSamp
                    bytestring[448:450].decode('utf-8'),                                # [45] A1 Not used.
                    bytestring[450:452].decode('utf-8'),                                # [46] B0 Not used.
                    bytestring[452:454].decode('utf-8'),                                # [47] B1 Not used.
                    binascii.hexlify(bytestring[454:456]),                              # [48] Spare
                    int.from_bytes(bytestring[456:458], 'little'),                      # [49] AnaOutScale
                    int.from_bytes(bytestring[458:460], 'little'),                      # [50] CorrThresh
                    binascii.hexlify(bytestring[460:462]),                              # [51] Spare
                    int.from_bytes(bytestring[462:464], 'little'),                      # [52] TiLag2
                    binascii.hexlify(bytestring[464:486]),                              # [53] Spare
                    bytestring[486:510]                                                 # [54] QualConst
                    )
            except Exception as err:
                utils.log(self.__qualname__, 'parse_usr_cfg', type(err).__name__, err)

        def filereader():
            #
            # Executed in a separate thread to not block scheduler.
            #
            try:
                with open(dfl.CONFIG_DIR + self.instrument_config, 'rb') as raw:
                    bytestring = raw.read()
                    self.hw_cfg = parse_hw_cfg(bytestring[0:48])         # Hardware config (48 bytes)
                    self.head_cfg = parse_head_cfg(bytestring[48:272])   # Head config (224 bytes)
                    self.usr_cfg = parse_usr_cfg(bytestring[272:784])    # Deployment config (512 bytes)
            except Exception as err:
                utils.log(self.__qualname__, 'parse_cfg', type(err).__name__, err)
            self.evt.set()

        _thread.start_new_thread(filereader, ())
        await asyncio.sleep_ms(10)
        await self.evt.wait()
        self.evt.clear()

    async def set_usr_cfg(self):
        # Uploads a deployment config to the instrument and sets up the cron job.
        bytestring = b''
        def filereader():
            nonlocal bytestring
            try:
                with open(dfl.CONFIG_DIR + self.deployment_config, 'rb') as pcf:
                    bytestring = pcf.read()
            except Exception as err:
                utils.log(self.__qualname__, 'set_usr_cfg', type(err).__name__, err)
            self.evt.set()

        def set_deployment_start(sampling_interval, avg_interval):
            # Computes the measurement starting time to be in synch with the scheduler.
            now = time.time()
            next_sampling = now - now % sampling_interval + sampling_interval
            utils.log(self.__qualname__, 'deployment start at {}, measurement interval {}\', average interval {}\''.format(utils.timestring(next_sampling), sampling_interval, avg_interval))
            deployment_start = time.localtime(next_sampling - avg_interval + self.deployment_delay)
            return binascii.unhexlify('{:02d}{:02d}{:02d}{:02d}{:02d}{:02d}'.format(deployment_start[4], deployment_start[5], deployment_start[2], deployment_start[3], int(str(deployment_start[0])[2:]), deployment_start[1]))

        if await self.brk():
            _thread.start_new_thread(filereader, ())
            await asyncio.sleep_ms(10)
            await self.evt.wait()
            self.evt.clear()
            if bytestring:
                sampling_interval = int.from_bytes(bytestring[38:40], 'little')
                avg_interval = int.from_bytes(bytestring[16:18], 'little')
                for _ in cfg.CRON:
                    if _[0] == self.__qualname__ + str(self.instance).lower():
                        if not _[9]:  # Skips if continuos polling.
                            _[7] = range(0,60,sampling_interval)
                usr_cfg = bytestring[0:48] + set_deployment_start(sampling_interval, avg_interval) + bytestring[54:510]
                checksum = await self.calc_checksum(usr_cfg)
                await self.swriter.awrite(b'\x43\x43')
                await self.swriter.awrite(usr_cfg + binascii.unhexlify(hex(checksum)[-2:] + hex(checksum)[2:4]))
                if await self.reply():
                    if self.ack():
                        return True
            utils.log(self.__qualname__, 'unable to upload the deployment configuration', type='e')
            return False

    async def start_delayed(self):

        async def format_recorder():
            if await self.brk():
                await self.swriter.awrite(b'\x46\x4F\x12\xD4\x1E\xEF')
                if await self.reply():
                    if self.ack():
                        utils.log(self.__qualname__, 'recorder formatted')
                        return True
            utils.log(self.__qualname__, 'unable to format the recorder', type='e')
            return False

        if await self.brk():
            while True:
                await self.swriter.awrite('SD')
                if await self.reply():
                    if self.ack():
                        return True
                    if await format_recorder():
                        await asyncio.sleep(0)
                        continue
                utils.log(self.__qualname__, 'unable to start measurement', type='e')
                return False

    def conv_data(self):

        def get_error(error):
            try:
                return(
                    'COMPASS {}'.format('ERROR' if error >> 0 & 1 else 'OK'),
                    'MEASUREMENT DATA {}'.format('ERROR' if error >> 1 & 1 else 'OK'),
                    'SENSOR DATA {}'.format('ERROR' if error >> 2 & 2 else 'OK'),
                    'TAG BIT {}'.format('ERROR' if error >> 3 & 1 else 'OK'),
                    'FLASH {}'.format('ERROR' if error >> 4 & 1 else 'OK'),
                    'BEAM NUMBER {}'.format('ERROR' if error >> 5 & 1 else 'OK'),
                    'COORD. TRANSF. {}'.format('ERROR' if error >> 3 & 1 else 'OK')
                    )
            except Exception as err:
                utils.log(self.__qualname__, 'get_error', type(err).__name__, err)

        def get_status(status):

            def get_wkup_state(status):
                try:
                    return (
                        'WKUP STATE {}'.format(
                            'BAD POWER' if ~ status >> 5 & 1 and ~ status >> 4 & 1 else
                            'POWER APPLIED' if ~ status >> 5 & 1 and status >> 4 & 1 else
                            'BREAK' if status >> 5 & 1 and ~ status >> 4 & 1 else
                            'RTC ALARM' if status >> 5 & 1 and status >> 4 & 1 else None)
                        )
                except Exception as err:
                    utils.log(self.__qualname__, 'get_wkup_state', type(err).__name__, err)

            def get_power_level(status):
                try:
                    return (
                        'POWER LEVEL {}'.format(
                            '0' if ~ status >> 7 & 1 and ~ status >> 6 & 1 else
                            '1' if ~ status >> 7 & 1 and status >> 6 & 1 else
                            '2' if status >> 7 & 1 and ~ status >> 6 & 1 else
                            '3' if status >> 7 & 1 and status >> 6 & 1 else None)
                        )
                except Exception as err:
                    utils.log(self.__qualname__, 'get_power_level', type(err).__name__, err)

            try:
                return(
                    '{}'.format('DOWN' if status >> 0 & 1 else 'UP'),
                    'SCALING {} mm/s'.format('0.1' if status >> 1 & 1 else '1'),
                    'PITCH {}'.format('OUT OF RANGE' if status >> 2 & 2 else 'OK'),
                    'ROLL {}'.format('OUT OF RANGE' if status >> 3 & 1 else 'OK'),
                    get_wkup_state(status),
                    get_power_level(status)
                    )
            except Exception as err:
                utils.log(self.__qualname__, 'get_status', type(err).__name__, err)

        def get_pressure(pressureMSB, pressureLSW):
            try:
                return 65536 * int.from_bytes(pressureMSB, 'little') + int.from_bytes(pressureLSW, 'little')
            except Exception as err:
                utils.log(self.__qualname__, 'get_pressure', type(err).__name__, err)

        def get_cells(data):
            # list(x1, x2, x3... y1, y2, y3... z1, z2, z3..., a11, a12 , a13..., a21, a22, a23..., a31, a32, a33...)
            try:
                if self.usr_cfg:
                    nbins = self.usr_cfg[18]
                    nbeams = self.usr_cfg[10]
                    j = 0
                    for beam in range(nbeams):
                        for bin in range(nbins):
                            yield struct.unpack('<h',data[j:j+2])[0]/1000
                            j += 2
                    for beam in range(nbeams):
                        for bin in range(nbins):
                            yield int.from_bytes(data[j:j+1], 'little')
                            j += 1
            except Exception as err:
                utils.log(self.__qualname__, 'get_cells', type(err).__name__, err)

        try:
            return (
                binascii.hexlify(self.data[4:5]),                          # [0] Minute
                binascii.hexlify(self.data[5:6]),                          # [1] Second
                binascii.hexlify(self.data[6:7]),                          # [2] Day
                binascii.hexlify(self.data[7:8]),                          # [3] Hour
                binascii.hexlify(self.data[8:9]),                          # [4] Year
                binascii.hexlify(self.data[9:10]),                         # [5] Month
                get_error(int.from_bytes(self.data[10:12],'little')),      # [6] Error code
                struct.unpack('<h',self.data[12:14])[0] / 10,              # [7] Analog input 1
                struct.unpack('<h',self.data[14:16])[0] / 10,              # [8] Battery voltage
                struct.unpack('<h',self.data[16:18])[0] / 10,              # [9] Soundspeed
                struct.unpack('<h',self.data[18:20])[0] / 10,              # [10] Heading
                struct.unpack('<h',self.data[20:22])[0] / 10,              # [11] Pitch
                struct.unpack('<h',self.data[22:24])[0] / 10,              # [12] Roll
                get_pressure(self.data[24:25], self.data[26:28]) / 1000,   # [13] Pressure
                get_status(int.from_bytes(self.data[25:26],'little')),     # [14] Status code
                struct.unpack('<h',self.data[28:30])[0] / 100,             # [15] Temperature
                ) + tuple(get_cells(self.data[30:]))                       # [16:] x1,y1,z1, x2, y2, z2, x3, y3, z3...
        except Exception as err:
            utils.log(self.__qualname__, 'conv_data', type(err).__name__, err)

    def format_data(self, sample):

        def get_flow():
            return 0  # TODO: calc flow for rivers.

        try:
            record = [
            self.config['String_Label'],
            '{:2s}/{:2s}/20{:2s}'.format(sample[2], sample[5], sample[4]),  # dd/mm/yyyy
            '{:2s}:{:2s}'.format(sample[3], sample[0]),                     # hh:mm
            '{:.2f}'.format(sample[8]),                                     # Battery
            '{:.2f}'.format(sample[9]),                                     # SoundSpeed
            '{:.2f}'.format(sample[10]),                                    # Heading
            '{:.2f}'.format(sample[11]),                                    # Pitch
            '{:.2f}'.format(sample[12]),                                    # Roll
            '{:.2f}'.format(sample[13]),                                    # Pressure
            '{:.2f}'.format(sample[15]),                                    # Temperature
            '{:.2f}'.format(get_flow()),                                    # Flow
            '{}'.format(self.usr_cfg[17]),                                  # CoordSystem
            '{}'.format(self.usr_cfg[4]),                                   # TODO: BlankingDistance
            '{}'.format(self.usr_cfg[20]),                                  # MeasInterval
            '{:.2f}'.format(self.usr_cfg[19] * 0.01692620176 / 100),        # BinLength
            '{}'.format(self.usr_cfg[18]),                                  # NBins
            '{}'.format(sample[14][0])                                      # TiltSensorMounting
            ]

            j = 16
            for bin in range(self.usr_cfg[18]):
                record.append('#{}'.format(bin + 1))                        # (#Cell number)
                for beam in range(self.usr_cfg[10]):
                    record.append('{:.3f}'.format(sample[j+beam*self.usr_cfg[18]]))
                j += 1
            return record
        except Exception as err:
            utils.log(self.__qualname__, 'format_data', type(err).__name__, err)

    def log(self):
        #with open('/sd/data/aquadopp.raw','ab') as raw:
        #    raw.write(self.data)
        utils.log_data(dfl.DATA_SEPARATOR.join(self.format_data(self.conv_data())))

    async def main(self, lock, tasks=[]):
        # Scheduled task.
        self.init_uart()
        pyb.LED(3).on()
        await self.parse_cfg()
        try:
            self.data = await asyncio.wait_for(self.sreader.read(1024), self.timeout)
        except asyncio.TimeoutError:
            self.data = b''
            utils.log(self.__qualname__, 'no data received', type='e')
        if self.data and self.data != b'\x00':
            async with lock:
                self.log()
        pyb.LED(3).off()
        self.uart.deinit()

    async def main_(self, lock, tasks=[]):
        # Continuos polling. DEBUG
        self.init_uart()
        await self.parse_cfg()
        poll_ = select.poll()  # Creates a poll object to listen to.
        poll_.register(self.uart, select.POLLIN)
        while True:
            poll = poll_.ipoll(0, 0)
            for stream in poll:
                self.data = stream[0].read()
                if self.data == b'\x00':
                    continue
                pyb.LED(3).on()
                async with lock:
                    self.log()
                pyb.LED(3).off()
                await asyncio.sleep(0)
            await asyncio.sleep(0)
