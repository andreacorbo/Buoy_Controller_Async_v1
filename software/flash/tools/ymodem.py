import uasyncio as asyncio
import time
import os
import _thread
from tools.functools import partial
from tools.utils import verbose, f_lock
import tools.shutil as shutil
from configs import dfl, cfg

#
# Protocol bytes
#
SOH = b'\x01'  # 1
STX = b'\x02'  # 2
EOT = b'\x04'  # 4
ACK = b'\x06'  # 6
NAK = b'\x15'  # 21
CAN = b'\x18'  # 24
C = b'\x43'  # 67


class YMODEM:
    #
    # crctab calculated by Mark G. Mendel, Network Systems Corporation
    #
    crctable = [
        0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7,
        0x8108, 0x9129, 0xa14a, 0xb16b, 0xc18c, 0xd1ad, 0xe1ce, 0xf1ef,
        0x1231, 0x0210, 0x3273, 0x2252, 0x52b5, 0x4294, 0x72f7, 0x62d6,
        0x9339, 0x8318, 0xb37b, 0xa35a, 0xd3bd, 0xc39c, 0xf3ff, 0xe3de,
        0x2462, 0x3443, 0x0420, 0x1401, 0x64e6, 0x74c7, 0x44a4, 0x5485,
        0xa56a, 0xb54b, 0x8528, 0x9509, 0xe5ee, 0xf5cf, 0xc5ac, 0xd58d,
        0x3653, 0x2672, 0x1611, 0x0630, 0x76d7, 0x66f6, 0x5695, 0x46b4,
        0xb75b, 0xa77a, 0x9719, 0x8738, 0xf7df, 0xe7fe, 0xd79d, 0xc7bc,
        0x48c4, 0x58e5, 0x6886, 0x78a7, 0x0840, 0x1861, 0x2802, 0x3823,
        0xc9cc, 0xd9ed, 0xe98e, 0xf9af, 0x8948, 0x9969, 0xa90a, 0xb92b,
        0x5af5, 0x4ad4, 0x7ab7, 0x6a96, 0x1a71, 0x0a50, 0x3a33, 0x2a12,
        0xdbfd, 0xcbdc, 0xfbbf, 0xeb9e, 0x9b79, 0x8b58, 0xbb3b, 0xab1a,
        0x6ca6, 0x7c87, 0x4ce4, 0x5cc5, 0x2c22, 0x3c03, 0x0c60, 0x1c41,
        0xedae, 0xfd8f, 0xcdec, 0xddcd, 0xad2a, 0xbd0b, 0x8d68, 0x9d49,
        0x7e97, 0x6eb6, 0x5ed5, 0x4ef4, 0x3e13, 0x2e32, 0x1e51, 0x0e70,
        0xff9f, 0xefbe, 0xdfdd, 0xcffc, 0xbf1b, 0xaf3a, 0x9f59, 0x8f78,
        0x9188, 0x81a9, 0xb1ca, 0xa1eb, 0xd10c, 0xc12d, 0xf14e, 0xe16f,
        0x1080, 0x00a1, 0x30c2, 0x20e3, 0x5004, 0x4025, 0x7046, 0x6067,
        0x83b9, 0x9398, 0xa3fb, 0xb3da, 0xc33d, 0xd31c, 0xe37f, 0xf35e,
        0x02b1, 0x1290, 0x22f3, 0x32d2, 0x4235, 0x5214, 0x6277, 0x7256,
        0xb5ea, 0xa5cb, 0x95a8, 0x8589, 0xf56e, 0xe54f, 0xd52c, 0xc50d,
        0x34e2, 0x24c3, 0x14a0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
        0xa7db, 0xb7fa, 0x8799, 0x97b8, 0xe75f, 0xf77e, 0xc71d, 0xd73c,
        0x26d3, 0x36f2, 0x0691, 0x16b0, 0x6657, 0x7676, 0x4615, 0x5634,
        0xd94c, 0xc96d, 0xf90e, 0xe92f, 0x99c8, 0x89e9, 0xb98a, 0xa9ab,
        0x5844, 0x4865, 0x7806, 0x6827, 0x18c0, 0x08e1, 0x3882, 0x28a3,
        0xcb7d, 0xdb5c, 0xeb3f, 0xfb1e, 0x8bf9, 0x9bd8, 0xabbb, 0xbb9a,
        0x4a75, 0x5a54, 0x6a37, 0x7a16, 0x0af1, 0x1ad0, 0x2ab3, 0x3a92,
        0xfd2e, 0xed0f, 0xdd6c, 0xcd4d, 0xbdaa, 0xad8b, 0x9de8, 0x8dc9,
        0x7c26, 0x6c07, 0x5c64, 0x4c45, 0x3ca2, 0x2c83, 0x1ce0, 0x0cc1,
        0xef1f, 0xff3e, 0xcf5d, 0xdf7c, 0xaf9b, 0xbfba, 0x8fd9, 0x9ff8,
        0x6e17, 0x7e36, 0x4e55, 0x5e74, 0x2e93, 0x3eb2, 0x0ed1, 0x1ef0,
    ]


    def __init__(self, agetc, aputc, tmp_pfx, sent_pfx, bkp_pfx, retry=3, timeout=10, mode='Ymodem', pad=b'\x1a'):
        self.agetc = agetc
        self.aputc = aputc
        self.tmp_pfx = tmp_pfx
        self.sent_pfx = sent_pfx
        self.bkp_pfx = bkp_pfx
        self.retry = retry
        self.timeout = timeout
        self.mode = mode
        self.pad = pad

    async def send(self, files):
        #
        # Sends a list of files.
        #
        event = asyncio.Event()  # Event to wait for threads completion.

        def datareader():
            #
            # Reads out n-bytes from the current file.
            #
            with open(self.file) as s:
                s.seek(self.pointer)
                self.data = s.read(self.packet_size)
                self.tpointer = s.tell()
            event.set()

        def set_last_byte():
            #
            # Writes out the last sent byte in the current temp file.
            #
            with open(self.tmp_file, 'w') as t:
                t.write(str(self.pointer))
            event.set()

        def get_last_byte():
            #
            # Gets the last sent byte from the current temp file and sets up the
            # pointer.
            #
            try:
                with open(self.tmp_file) as t:
                    self.pointer = int(t.read())
            except:
                self.pointer = 0
            event.set()

        async def bkp_file():
            #
            # Makes a copy of the current file if it is the daily file.
            #
            bkp = self.file.replace(self.file.split('/')[-1], self.bkp_pfx + self.file.split('/')[-1])
            async with f_lock:
                shutil.copyfile(self.file, bkp)
            return bkp

        def filename_pkt_hdr():
            b = []
            if self.packet_size == 128:
                b.append(ord(SOH))
            elif self.packet_size == 1024:
                b.append(ord(STX))
            b.extend([0x00, 0xff])
            return bytearray(b)

        def data_pkt_hdr():
            assert self.packet_size in (128, 1024), self.packet_size
            b = []
            if self.packet_size == 128:
                b.append(ord(SOH))
            elif self.packet_size == 1024:
                b.append(ord(STX))
            b.extend([self.sequence, 0xff - self.sequence])
            return bytearray(b)

        def make_checksum():
            b = []
            if self.crc_mode:
                crc = calc_crc()
                b.extend([crc >> 8, crc & 0xff])
            else:
                crc = calc_checksum()
                b.append(crc)
            self.checksum = bytearray(b)
            event.set()

        def calc_checksum():
            return (sum(map(ord, self.data)) + self.checksum) % 256

        def calc_crc(crc=0):
            #Calculates the 16 bit Cyclic Redundancy Check for a given block of data.
            for char in bytearray(self.data):
                crctbl_idx = ((crc >> 8) ^ char) & 0xff
                crc = ((crc << 8) ^ self.crctable[crctbl_idx]) & 0xffff
            return crc & 0xffff

        def totally_sent():

            def is_new_day():
                now = time.time() - time.time() % 86400
                try:
                    last_file_write = os.stat(self.file)[8] - os.stat(self.file)[8] % 86400
                    if now - last_file_write >= 86400:
                        return True
                    return False
                except:
                    return False

            if is_new_day():
                try:
                    os.rename(self.file, self.sent_file)
                    try:
                        os.remove(self.tmp_file)
                    except:
                        verbose('UNABLE TO REMOVE {} FILE'.format(self.tmp_file))
                except:
                    verbose('UNABLE TO RENAME {} FILE'.format(self.file))

        async def begin_transmission():
            try:
                self.packet_size = dict(Ymodem = 128, Ymodem1k = 1024)[self.mode]
            except KeyError:
                raise ValueError('INVALID MODE {}'.format(self.mode))
            verbose('BEGIN TRANSACTION, PACKET SIZE {}'.format(self.packet_size))
            error_count = 0
            self.crc_mode = 0
            while True:
                char = await self.agetc(1, self.timeout)
                if error_count == self.retry:
                    verbose('TOO MANY ERRORS, ABORTING...')
                    return False
                elif not char:
                    verbose('TIMEOUT OCCURRED WHILE WAITING FOR STARTING TRANSMISSION, RETRY...')
                    error_count += 1
                elif char == C:
                    verbose('<-- C')
                    verbose('16 BIT CRC REQUESTED')
                    self.crc_mode = 1
                    error_count = 0
                    return True
                elif char == NAK:
                    verbose('<-- NAK')
                    verbose('STANDARD CECKSUM REQUESTED')
                    self.crc_mode = 0
                    error_count = 0
                    return True
                else:
                    verbose('UNATTENDED CHAR {}, RETRY...'.format(char))
                    error_count += 1
                await asyncio.sleep(0)

        async def file_handler():
            self.tmp_file = self.file.replace(self.file.split('/')[-1], self.tmp_pfx + self.file.split('/')[-1])
            self.sent_file = self.file.replace(self.file.split('/')[-1], self.sent_pfx + self.file.split('/')[-1])
            self.filename = self.file.split('/')[-1]
            if self.file != '\x00':
                self.filename = cfg.HOSTNAME.lower() + '/' + self.file.split('/')[-1]  # Adds system name to filename.
                if self.file.split('/')[-1] == cfg.DATA_FILE:
                    self.file = await bkp_file()
                #try:
                #    stream = open(self.file)
                #except:
                #    verbose('UNABLE TO OPEN {}, TRY NEXT self.file...'.format(self.file))
                #    return  # open next self.file
                _thread.start_new_thread(get_last_byte, ())  # read last byte from $self.file
                await asyncio.sleep_ms(10)
                await event.wait()
                event.clear()
                if self.pointer == int(os.stat(self.file)[6]):  # check if pointer correspond to self.file size
                    verbose('self.file {} ALREADY TRANSMITTED, SEND NEXT self.file...'.format(self.filename))
                    totally_sent()
                    return False # open next file
            return True

        async def clear_to_send():
            error_count = 0
            while error_count < self.retry:
                char = await self.agetc(1, self.timeout)
                if not char:
                    verbose('TIMEOUT OCCURRED, RETRY...')
                    error_count += 1
                elif char == C:
                    verbose('<-- C')
                    return True
                else:
                    verbose('UNATTENDED CHAR {}, RETRY...'.format(char))
                    error_count += 1
                await asyncio.sleep(0)
            verbose('TOO MANY ERRORS, ABORTING...')
            return  False

        async def filename_pkt():

            def stat_file():
                self.stat_file = os.stat(self.file)
                event.set()

            self.header = filename_pkt_hdr()  # create self.file packet
            self.data = bytearray(self.filename + '\x00', 'utf8')  # self.filename + space
            if self.file != '\x00':
                _thread.start_new_thread(stat_file, ())  # read last byte from $self.file
                await asyncio.sleep_ms(10)
                await event.wait()
                event.clear()
                self.data.extend((
                    str(self.stat_file[6] - self.pointer) +
                    ' ' +
                    str(self.stat_file[8])
                    ).encode('utf8'))  # Sends data size and mod date to be transmitted

            padding = bytearray(self.packet_size - len(self.data))  # fill packet size with null char

            self.data.extend(padding)

            _thread.start_new_thread(make_checksum,())
            await asyncio.sleep_ms(10)
            await event.wait()
            event.clear()


        async def send_filename_pkt():
            await asyncio.sleep(0.1)

            async def send():
                error_count = 0
                await asyncio.sleep(0)
                while error_count < self.retry:
                    if not await self.aputc(self.header + self.data + self.checksum, self.timeout):  # handle tx errors
                        error_count += 1
                        await asyncio.sleep(0)
                        continue
                    verbose('SENDING FILE {}'.format(self.filename))
                    return True
                verbose('TOO MANY ERRORS, ABORTING...')
                return  False

            async def reply():
                error_count = 0
                cancel = 0
                while error_count < self.retry:
                    char = await self.agetc(1, self.timeout)
                    if not char:  # handle rx erros
                        verbose('TIMEOUT OCCURRED, RETRY...')
                        error_count += 1
                        return 'resend'
                    elif char == ACK :
                        verbose('<-- ACK TO FILE {}'.format(self.filename))
                        if self.data == bytearray(self.packet_size):
                            verbose('TRANSMISSION COMPLETE, EXITING...')
                        return True
                    elif char == CAN:
                        verbose('<-- CAN')
                        if cancel:
                            verbose('TRANSMISSION CANCELED BY RECEIVER')
                            return  False
                        else:
                            cancel = 1
                            await asyncio.sleep(0)
                            continue  # wait for a second CAN
                    else:
                        verbose('UNATTENDED CHAR {}, RETRY...'.format(char))
                        error_count += 1
                        return 'resend'
                verbose('TOO MANY ERRORS, ABORTING...')
                return  False

            while True:
                if not await send():
                    return False
                res = await reply()
                if not res:
                    return False
                if res == 'resend':
                    await asyncio.sleep(0)
                    continue
                return True

        async def send_data():
            self.success_count = 0
            self.total_packets = 0
            self.sequence = 1
            self.cancel = 0
            async def data_pkt():
                _thread.start_new_thread(datareader,())
                await asyncio.sleep_ms(10)
                await event.wait()
                event.clear()
                if not self.data:  # EOF.
                    verbose('EOF')
                    return False
                self.total_packets += 1
                self.header = data_pkt_hdr()
                format_string = '{:'+self.pad.decode('utf-8')+'<'+str(self.packet_size)+'}'  # right fill data with pad byte
                self.data = format_string.format(self.data)
                self.data = self.data.encode('utf8')
                _thread.start_new_thread(make_checksum,())
                await asyncio.sleep_ms(10)
                await event.wait()
                event.clear()
                return True

            async def send():
                error_count = 0
                while error_count < self.retry:
                    if not await self.aputc(self.header + self.data + self.checksum, self.timeout):  # handle tx errors
                        error_count += 1
                        await asyncio.sleep(0)
                        continue  # resend packet
                    verbose('PACKET {} -->'.format(self.sequence))
                    return True
                verbose('TOO MANY ERRORS, ABORTING...')
                return  False

            async def reply():
                error_count = 0
                cancel = 0
                while error_count < self.retry:
                    await asyncio.sleep(0)
                    char = await self.agetc(1, self.timeout)
                    await asyncio.sleep(0)
                    if not char:  # handle rx errors
                        verbose('TIMEOUT OCCURRED, RETRY...')
                        return 'resend'
                    elif char == ACK:
                        await asyncio.sleep(0)
                        verbose('<-- ACK TO PACKET {}'.format(self.sequence))
                        await asyncio.sleep(0)
                        self.success_count += 1
                        await asyncio.sleep(0)
                        self.pointer = self.tpointer  # Updates pointer
                        _thread.start_new_thread(set_last_byte, ())  # keep track of last successfully transmitted packet
                        await asyncio.sleep_ms(10)
                        await event.wait()
                        event.clear()
                        await asyncio.sleep(0)
                        self.sequence = (self.sequence + 1) % 0x100  # keep track of sequence
                        await asyncio.sleep(0)
                        return True
                    elif char == NAK:
                        verbose('<-- NAK')
                        return 'resend'
                    elif char == CAN:
                        verbose('<-- CAN')
                        if cancel:
                            verbose('TRANSMISSION CANCELED BY RECEIVER')
                            return  False
                        else:
                            cancel = 1
                            await asyncio.sleep(0)
                            continue  # wait for a second CAN
                    else:
                        verbose('UNATTENDED CHAR {}, RETRY...'.format(char))
                        return 'resend'
                    await asyncio.sleep(0)
                verbose('TOO MANY ERRORS, ABORTING...')
                return  False

            while True:
                if not await data_pkt():
                    return True
                while True:
                    if not await send():
                        return False
                    res = await reply()
                    if not res:
                        return False
                    elif res == 'resend':
                        await asyncio.sleep(0)
                        continue
                    break

        async def end_transmission():
            error_count = 0
            while error_count < self.retry:
                if not await self.aputc(EOT, self.timeout):  # handle tx errors
                    error_count += 1
                    await asyncio.sleep(0)
                    continue  # resend EOT
                verbose('EOT -->')
                await asyncio.sleep(0)
                char = await self.agetc(1, self.timeout)  # waiting for reply
                if not char:  # handle rx errors
                    verbose('TIMEOUT OCCURRED WHILE WAITING FOR REPLY TO EOT, RETRY...')
                    error_count += 1
                elif char == ACK:
                    verbose('<-- ACK TO EOT')
                    verbose('FILE {} SUCCESSFULLY TRANSMITTED'.format(self.filename))
                    totally_sent()
                    return True
                else:
                    verbose('UNATTENDED CHAR {}, RETRY...'.format(char))
                    error_count += 1
                await asyncio.sleep(0)
            verbose('TOO MANY ERRORS, ABORTING...')
            return False

        ####################### Starts transmission. ###########################
        if not await begin_transmission():
            return False
        count = 0
        for file in files:
            self.file = file
            if not await file_handler():
                await asyncio.sleep(0)
                continue
            count += 1
            if count > 1:
                if not await clear_to_send():
                    return False
            await asyncio.sleep(0)
            await filename_pkt()
            await asyncio.sleep(0)
            if not await send_filename_pkt():
                return False
            if self.file == '\x00':
                return True
            if not await clear_to_send():
                return False
            if not await send_data():
                return False
            if not await end_transmission():
                return False
        return True

    async def abort(self, count=2):
        verbose('CANCEL TRANSMISSION...')
        for _ in range(count):
            await self.aputc(CAN, 60)  # handle tx errors
            verbose('CAN -->')
            await asyncio.sleep(0)

    async def ack(self):
        error_count = 0
        while error_count < self.retry:
            if not await self.aputc(ACK, self.timeout):  # handle tx errors
                verbose('ERROR SENDING ACK, RETRY...')
                error_count += 1
                await asyncio.sleep(0)
                continue
            verbose('ACK -->')
            return True
        verbose('TOO MANY ERRORS, ABORTING...')
        return False  # Exit

    async def nak(self):
        error_count = 0
        while error_count < self.retry:
            if not await self.aputc(NAK, self.timeout):  # handle tx errors
                verbose('ERROR SENDING NAK, RETRY...')
                error_count += 1
                await asyncio.sleep(0)
                continue
            verbose('NAK -->')
            return False  # Exit
        return True
        verbose('TOO MANY ERRORS, ABORTING...')

    async def clear(self):
        error_count = 0
        while error_count < self.retry:
            if not await self.aputc(C, self.timeout):  # handle tx errors
                verbose('ERROR SENDING C, RETRY...')
                error_count += 1
                await asyncio.sleep(0)
                continue
            verbose('C -->')
            return True
        verbose('TOO MANY ERRORS, ABORTING...')
        return False  # Exit

    def verify_recvd_checksum(self):
        if self.crc_mode:
            self.checksum = bytearray(self.data[-2:])
            received_sum = (self.checksum[0] << 8) + self.checksum[1]
            calculated_sum = await self.calc_crc(self.data[:-2])
            valid = bool(received_sum == calculated_sum)
            if not valid:
                verbose('CHECKSUM FAIL EXPECTED({:04x}) GOT({:4x})'.format(received_sum, calculated_sum))
        else:
            self.checksum = bytearray([self.data[-1]])
            received_sum = self.checksum[0]
            calculated_sum = self.calc_checksum(self.data[-1])
            valid = received_sum == calculated_sum
            if not valid:
                verbose('CHECKSUM FAIL EXPECTED({:02x}) GOT({:2x})'.format(received_sum, calculated_sum))
        return valid


YMODEM1k = partial(YMODEM, mode='Ymodem1k')
