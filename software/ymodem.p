import uasyncio as asyncio
import time
import os
import sys
from tools.functools import partial
import tools.utils as utils
import tools.shutil as shutil
from configs import dfl, cfg

#
# Protocol bytes
#
SOH = b"\x01"  # 1
STX = b"\x02"  # 2
EOT = b"\x04"  # 4
ACK = b"\x06"  # 6
NAK = b"\x15"  # 21
CAN = b"\x18"  # 24
C = b"\x43"  # 67


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


    def __init__(self, _getc, _putc, mode="Ymodem", pad=b"\x1a"):
        self._getc = _getc
        self._putc = _putc
        self.mode = mode
        self.pad = pad

    def recv(self, timeout=10, retry=3, crc_mode=1):
        """Receives files according to ymodem protocol.

        Params:
            retry(int): default[3]
            timeout(int): seconds, default[10]
        """
        #
        # Initialize transaction
        #
        error_count = 0
        while error_count < retry:
            restart = False
            while True:
                if crc_mode:
                    #
                    # Send C to request 16 bit CRC as first choice
                    #
                    while True:
                        if error_count > (retry // 2):
                            print("TOO MANY ERRORS, USE STANDARD CHECKSUM...")
                            crc_mode = 0
                            error_count = 0
                            break
                        if not self._putc(C):  # handle tx errors
                            print("ERROR SENDING C, RETRY...")
                            error_count += 1
                            continue
                        print("C -->")
                        #error_count = 0
                        break
                else:
                    #
                    # Send NAK to request standard checksum as fall back
                    #
                    if not self.nak(error_count, retry):
                        return False  # Exits
                    error_count = 0
                break
            #
            # Receive packet
            #
            char = 0
            packet_size = 128
            cancel = 0
            sequence = 0
            income_size = 0
            while True:
                t0 = time.time()
                while not self.uart.any():
                    if time.time() - t0 >= timeout:  # Exits if sender does not respond
                        restart = True
                        error_count += 1
                        break
                    pass
                if restart:
                    break
                char = self._getc(1,timeout)
                if error_count == retry:
                    print("TOO MANY ERRORS, ABORTING...")
                    self.abort(timeout=timeout)  # Cancels transmission
                    return False  # Exits
                elif not char:  # handle rx errors
                    print("TIMEOUT OCCURRED, RETRY...")
                    error_count += 1
                    continue
                elif char == CAN:
                    print("<-- CAN")
                    if cancel:
                        print("TRANSMISSION CANCELED BY SENDER")
                        return False  # Exits
                    else:
                        cancel = 1
                        error_count = 0
                elif char == SOH:
                    print("SOH <--")
                    if packet_size != 128:
                        print("USING 128 BYTES PACKET SIZE")
                        packet_size = 128
                    error_count = 0
                elif char == STX:
                    print("STX <--")
                    if packet_size != 1024:
                        print("USING 1 KB PACKET SIZE")
                        packet_size = 1024
                    error_count = 0
                elif char == EOT:
                    print("EOT <--")
                    #
                    # Acknowledge EOT
                    #
                    if not self.ack(error_count, retry):
                        return False  # Exits
                    error_count = 0
                    sequence = 0
                    income_size = 0
                    #
                    # Clear to receive
                    #
                    if not self.clear(error_count, retry):
                        return False  # Exits
                    error_count = 0
                    continue
                else:
                    print("UNATTENDED CHAR {}".format(char))
                    error_count += 1
                    continue
                #
                # Read sequence
                #
                while True:
                    seq1 = self._getc(1, timeout)
                    if not seq1:
                        print("FAILED TO GET FIRST SEQUENCE BYTE")
                        seq2 = None
                    else:
                        seq1 = ord(seq1)
                        seq2 = self._getc(1, timeout)
                        if not seq2:
                            print("FAILED TO GET SECOND SEQUENCE BYTE")
                        else:
                            seq2 = 0xff - ord(seq2)
                            print("PACKET {} <--".format(sequence))
                    if not (seq1 == seq2 == sequence):
                        print("SEQUENCE ERROR, EXPECTED {} GOT {}, DISCARD DATA".format(sequence, seq1))
                        self._getc(packet_size + 1 + crc_mode)  # Discard data packet
                        #
                        # Resend missed acknowledge
                        #
                        if not self.ack(error_count, retry):
                            return False  # Exits
                        error_count += 1
                        #
                        # If receiving file name packet, clear for transmission
                        #
                        if seq1 == 0:
                            #
                            # Clear to receive
                            #
                            if not self.clear(error_count, retry):
                                return False  # Exits
                            error_count = 0
                    else:
                        data = self._getc(packet_size + 1 + crc_mode, timeout)
                        valid, data = self.verify_recvd_checksum(crc_mode, data)
                        if not valid:
                            #
                            # Not aknowledge packet, request retransmission
                            #
                            if not self.nak(error_count, retry):
                                return False  # Exits
                            error_count = 0
                        else:
                            if sequence == 0:  # Sequence 0 contains file name
                                if data[0:1] == b"\x00":  # Sequence 0 with null pathname state end of trasmission
                                    #
                                    # Acknowledge EOT
                                    #
                                    if not self.ack(error_count, retry):
                                        return False  # Exits
                                    print("END OF TRANSMISSION")
                                    return True  # Exits end of transmission
                                data_string = []
                                data_field = ""
                                for byte_ in data:
                                    if byte_ != 0:
                                        data_field += chr(byte_)
                                    elif len(data_field) > 0:
                                        data_string.append(data_field)
                                        data_field = ""
                                pathname = data_string[0]
                                file_size = int(data_string[1].split(" ")[0])
                                mod_date = int(data_string[1].split(" ")[1])
                                mode = "wb"  # Overwrite local.
                                try:  # File exists
                                    if utils.unix_epoch(os.stat(pathname)[8]) > mod_date:
                                        if os.stat(pathname)[6] < file_size:  # Local file is incomplete.
                                            mode = "ab"   # Append to local.
                                except:  # File doesn't exist.
                                    pass
                                stream = open(pathname, mode)
                                if stream:
                                    print("RECEIVING FILE {}".format(pathname))
                                    #
                                    # Acknowledge packet
                                    #
                                    if not self.ack(error_count, retry):
                                        return False  # Exits
                                    error_count = 0
                                    #
                                    # Clear for transmission
                                    #
                                    if not self.clear(error_count, retry):
                                        return False  # Exits
                                    error_count = 0
                                else:
                                    self.abort(timeout=timeout)  # Cancel transmission if file cannot be opened
                                    return False  # Exits
                            else:
                                income_size += len(data)
                                trailing_null = income_size - file_size  # null trailing char
                                stream.write(data[:-trailing_null])  # exclude null trailing chars
                                #
                                # Acknowledge packet
                                #
                                if not self.ack(error_count, retry):
                                    return False  # Exits
                                error_count = 0
                            sequence = (sequence + 1) % 0x100
                    break

    async def send(self, files, tmp_file_pfx, sent_file_pfx, bkp_file_pfx, lock, retry=3, timeout=10):
        """Sends files according to ymodem protocol.

        Params:
            files(list)
            tmp_file_pfx(str)
            sent_file_pfx(str)
            retry(int): default[5]
            timeout(int): seconds, default[10]
        """
        #
        # Initialize transaction
        #
        try:
            packet_size = dict(Ymodem = 128, Ymodem1k = 1024)[self.mode]
        except KeyError:
            raise ValueError("INVALID MODE {self.mode}".format(self=self))
        error_count = 0
        crc_mode = 0
        cancel = 0
        print("BEGIN TRANSACTION, PACKET SIZE {}".format(packet_size))
        #
        # Set 16 bit CRC or standard checksum mode
        #
        while True:
            char = self._getc(1, timeout)
            if error_count == retry:
                print("TOO MANY ERRORS, ABORTING...")
                return False  # Exit
            elif not char:
                print("TIMEOUT OCCURRED WHILE WAITING FOR STARTING TRANSMISSION, RETRY...")
                error_count += 1
            elif char == C:
                print("<-- C")
                print("16 BIT CRC REQUESTED")
                crc_mode = 1
                error_count = 0
                break
            elif char == NAK:
                print("<-- NAK")
                print("STANDARD CECKSUM REQUESTED")
                crc_mode = 0
                error_count = 0
                break
            else:
                print("UNATTENDED CHAR {}, RETRY...".format(char))
                error_count += 1
            await asyncio.sleep(0)
        #
        # Iterate over file list
        #
        #files.extend("\x00")  # add a null file to list to handle eot
        file_count = 0
        for file in sorted(files, reverse=True):
            #
            # Set stream pointer (read file from last tansmitted byte)
            #
            tmp_file = file.replace(file.split("/")[-1], tmp_file_pfx + file.split("/")[-1])
            sent_file = file.replace(file.split("/")[-1], sent_file_pfx + file.split("/")[-1])
            filename = file.split("/")[-1]
            if file != "\x00":
                filename = cfg.HOSTNAME.lower() + "/" + filename  # Adds system name to filename.
                try:
                    if filename == str(eval(cfg.DATA_FILE)):
                        file = await self.bkp_file(file, bkp_file_pfx, lock)
                    stream = open(file)
                except:
                    print("UNABLE TO OPEN {}, TRY NEXT FILE...".format(file))
                    continue
                self.get_last_byte(tmp_file, stream)  # read last byte from .file
                pointer = stream.tell()  # set stream pointer
                if pointer == os.stat(file)[6]:  # check if pointer correspond to file size
                    print("FILE {} ALREADY TRANSMITTED, SEND NEXT FILE...".format(filename))
                    stream.close()
                    self.totally_sent(file, tmp_file, sent_file)
                    continue  # open next file
            file_count += 1
            #
            # Wait for clear to send (if there are more than one file)
            #
            if file_count > 1:
                while True:
                    char = self._getc(1, timeout)
                    if error_count == retry:
                        print("TOO MANY ERRORS, ABORTING...")
                        return False  # Exit
                    if not char:  # handle rx errors
                        print("TIMEOUT OCCURRED WHILE WAITING FOR SEND HEADER PACKET, RETRY...")
                        error_count += 1
                    elif char == C:
                        print("<-- C")
                        error_count = 0
                        break
                    else:
                        print("UNATTENDED CHAR {}, RETRY...".format(char))
                        error_count += 1
                    await asyncio.sleep(0)
            #
            # Create file name packet
            #
            header = self.make_filename_header(packet_size)  # create file packet

            data = bytearray(filename + "\x00", "utf8")  # filename + space
            if file != "\x00":
                data.extend(str(os.stat(file)[6] - pointer).encode("utf8"))  # Sends data size to be transmitted
            padding = bytearray(packet_size - len(data))  # fill packet size with null char
            data.extend(padding)
            checksum = await self.make_checksum(crc_mode, data)  # create packet checksum
            ackd  = 0
            while True:
                #
                # Send packet
                #
                while True:
                    if error_count == retry:
                        print("TOO MANY ERRORS, ABORTING...")
                        return False  # Exit
                    if not self._putc(header + data +checksum):  # handle tx errors
                        error_count += 1
                        continue
                    print("SENDING FILE {}".format(filename))
                    break
                    await asyncio.sleep(0)
                #
                # Wait for reply
                #
                while True:
                    char = self._getc(1, timeout)
                    if error_count == retry:
                        print("TOO MANY ERRORS, ABORTING...")
                        return False  # Exit
                    if not char:  # handle rx erros
                        print("TIMEOUT OCCURRED WHILE WAITING FOR REPLY TO HEADER PACKET, RETRY...")
                        error_count += 1
                        break  # resend packet
                    elif char == ACK :
                        print("<-- ACK")
                        if data == bytearray(packet_size):
                            print("TRANSMISSION COMPLETE, EXITING...")
                            return True # Exit
                        else:
                            error_count = 0
                            ackd = 1
                            break
                    elif char == CAN:
                        print("<-- CAN")
                        if cancel:
                            print("TRANSMISSION CANCELED BY RECEIVER")
                            return False  # Exit
                        else:
                            cancel = 1
                            error_count = 0
                            continue  # wait for a second CAN
                    else:
                        print("UNATTENDED CHAR {}, RETRY...".format(char))
                        error_count += 1
                        break  # resend packet
                    await asyncio.sleep(0)
                if ackd:
                    break  # wait for data
            #
            # Waiting for clear to send
            #
            while True:
                char = self._getc(1, timeout)
                if error_count == retry:
                    print("TOO MANY ERRORS, ABORTING...")
                    return False # Exit
                if not char:  # handle rx errors
                    print("TIMEOUT OCCURRED WHILE WAITING FOR SEND DATA PACKET, RETRY...")
                    error_count += 1
                elif char == C:
                    print("<-- C")
                    error_count = 0
                    break
                else:
                    print("UNATTENDED CHAR {}, RETRY...".format(char))
                    error_count += 1
                await asyncio.sleep(0)
            #
            # Send file
            #
            success_count = 0
            total_packets = 0
            sequence = 1
            cancel = 0
            while True:
                #
                # Create data packet
                #
                data = stream.read(packet_size)  # read a bytes packet

                if not data:  # file reached eof send eot
                    print("EOF")
                    break
                total_packets += 1

                header = self.make_data_header(packet_size, sequence)  # create header
                format_string = "{:"+self.pad.decode("utf-8")+"<"+str(packet_size)+"}"  # right fill data with pad byte
                data = format_string.format(data)  # create packet data
                checksum = await self.make_checksum(crc_mode, data)  # create checksum
                ackd = 0
                while True:
                    #
                    # Send data packet
                    #
                    while True:
                        if error_count == retry:
                            print("TOO MANY ERRORS, ABORTING...")
                            return False  # Exit
                        if not self._putc(header + data + checksum):  # handle tx errors
                            error_count += 1
                            continue  # resend packet
                        print("PACKET {} -->".format(sequence))
                        break
                        await asyncio.sleep(0)
                    #
                    # Wait for reply
                    #
                    while True:
                        char = self._getc(1, timeout)
                        if not char:  # handle rx errors
                            print("TIMEOUT OCCURRED WHILE WAITING FOR REPLY TO DATA PACKET, RETRY...")
                            error_count += 1
                            break  # resend packet
                        elif char == ACK:
                            print("<-- ACK")
                            ackd = 1
                            success_count += 1
                            error_count = 0
                            pointer = stream.tell()  # move pointer to next packet start byte
                            self.set_last_byte(tmp_file, pointer)  # keep track of last successfully transmitted packet
                            sequence = (sequence + 1) % 0x100  # keep track of sequence
                            break  # send next packet
                        elif char == NAK:
                            print("<-- NAK")
                            error_count += 1
                            break  # resend packet
                        elif char == CAN:
                            print("<-- CAN")
                            if cancel:
                                print("TRANSMISSION CANCELED BY RECEIVER")
                                return False  # Exit
                            else:
                                cancel = 1
                                error_count = 0
                        else:
                            print("UNATTENDED CHAR {}, RETRY...".format(char))
                            error_count += 1
                            break  # resend packet
                        await asyncio.sleep(0)
                    if ackd:
                        break  # send next packet
                    await asyncio.sleep(0)
            #
            # End of transmission
            #
            while True:
                if error_count == retry:
                    print("TOO MANY ERRORS, ABORTING...")
                    return False  # Exit
                if not self._putc(EOT):  # handle tx errors
                    error_count += 1
                    continue  # resend EOT
                print("EOT -->")
                char = self._getc(1, timeout)  # waiting for reply
                if not char:  # handle rx errors
                    print("TIMEOUT OCCURRED WHILE WAITING FOR REPLY TO EOT, RETRY...")
                    error_count += 1
                elif char == ACK:
                    print("<-- ACK")
                    print("FILE {} SUCCESSFULLY TRANSMITTED".format(filename))
                    self.totally_sent(file, tmp_file, sent_file)
                    stream.close()
                    error_count = 0
                    break  # send next file
                else:
                    print("UNATTENDED CHAR {}, RETRY...".format(char))
                    error_count += 1
                await asyncio.sleep(0)
            await asyncio.sleep(0)

    async def abort(self, count=2, timeout=60):
        print("CANCEL TRANSMISSION...")
        for _ in range(count):
            self._putc(CAN, timeout)  # handle tx errors
            print("CAN -->")
            await asyncio.sleep(0)

    async def ack(self, error_count, retry):
        while True:
            if error_count == retry:
                print("TOO MANY ERRORS, ABORTING...")
                return False  # Exit
            if not self._putc(ACK):  # handle tx errors
                print("ERROR SENDING ACK, RETRY...")
                error_count += 1
                continue
            print("ACK -->")
            break
            await asyncio.sleep(0)
        return True

    async def nak(self, error_count, retry):
        while True:
            if error_count == retry:
                print("TOO MANY ERRORS, ABORTING...")
                return False  # Exit
            if not self._putc(NAK):  # handle tx errors
                print("ERROR SENDING NAK, RETRY...")
                error_count += 1
                continue
            print("NAK -->")
            break
            await asyncio.sleep(0)
        return True

    async def clear(self, error_count, retry):
        while True:
            if error_count == retry:
                print("TOO MANY ERRORS, ABORTING...")
                return False  # Exit
            if not self._putc(C):  # handle tx errors
                print("ERROR SENDING C, RETRY...")
                error_count += 1
                continue
            print("C -->")
            break
            await asyncio.sleep(0)
        return True

    async def verify_recvd_checksum(self, crc_mode, data):
        if crc_mode:
            _checksum = bytearray(data[-2:])
            received_sum = (_checksum[0] << 8) + _checksum[1]
            data = data[:-2]
            calculated_sum = await self.calc_crc(data)
            valid = bool(received_sum == calculated_sum)
            if not valid:
                print("CHECKSUM FAIL EXPECTED({:04x}) GOT({:4x})".format(received_sum, calculated_sum))
        else:
            _checksum = bytearray([data[-1]])
            received_sum = _checksum[0]
            data = data[:-1]

            calculated_sum = self.calc_checksum(data)
            valid = received_sum == calculated_sum
            if not valid:
                print("CHECKSUM FAIL EXPECTED({:02x}) GOT({:2x})".format(received_sum, calculated_sum))
        return valid, data

    def set_last_byte(self, tmp_file, pointer):
        with open(tmp_file, "w") as part:
            part.write(str(pointer))

    def get_last_byte(self, tmp_file, stream):
        pointer = 0
        try:
            with open(tmp_file, "r") as part:
                pointer = int(part.read())
        except:
            pass
        stream.seek(pointer)

    def is_new_day(self, file):
        now = time.time() - time.time() % 86400
        try:
            last_file_write = os.stat(file)[8] - os.stat(file)[8] % 86400
            if now - last_file_write >= 86400:
                return True
            return False
        except:
            return False

    def totally_sent(self, file, tmp_file, sent_file):
        if self.is_new_day(file):
            try:
                os.rename(file, sent_file)
                try:
                    os.remove(tmp_file)
                except:
                    print("UNABLE TO REMOVE {} FILE".format(tmp_file))
            except:
                print("UNABLE TO RENAME {} FILE".format(file))

    def make_filename_header(self, packet_size):
        _bytes = []
        if packet_size == 128:
            _bytes.append(ord(SOH))
        elif packet_size == 1024:
            _bytes.append(ord(STX))
        _bytes.extend([0x00, 0xff])
        return bytearray(_bytes)

    def make_data_header(self, packet_size, sequence):
        assert packet_size in (128, 1024), packet_size
        _bytes = []
        if packet_size == 128:
            _bytes.append(ord(SOH))
        elif packet_size == 1024:
            _bytes.append(ord(STX))
        _bytes.extend([sequence, 0xff - sequence])
        return bytearray(_bytes)

    async def make_checksum(self, crc_mode, data):
        _bytes = []
        if crc_mode:
            crc = await self.calc_crc(data)
            _bytes.extend([crc >> 8, crc & 0xff])
        else:
            crc = self.calc_checksum(data)
            _bytes.append(crc)
        return bytearray(_bytes)

    def calc_checksum(self, data, checksum=0):
        return (sum(map(ord, data)) + checksum) % 256

    async def calc_crc(self, data, crc=0):
        """Calculates the 16 bit Cyclic Redundancy Check for a given block of data."""
        for char in bytearray(data):
            crctbl_idx = ((crc >> 8) ^ char) & 0xff
            crc = ((crc << 8) ^ self.crctable[crctbl_idx]) & 0xffff
            await asyncio.sleep(0)
        return crc & 0xffff

    ############################ Buoy Controller ###############################

    async def bkp_file(self, file, bkp_pfx, lock):  # TODO
        bkp = file.replace(file.split("/")[-1], bkp_pfx + file.split("/")[-1])
        if file.split("/")[-1] == str(eval(cfg.DATA_FILE)):  # Acquires the lock to safe handling the current data file.
            async with lock:
                try:
                    shutil.copyfile(file, bkp)  # Makes a backup copy of the file.
                    return bkp
                except:
                    print("UNABLE TO BACKUP {}".format(file))

YMODEM1k = partial(YMODEM, mode="Ymodem1k")
