uart = pyb.UART(4,9600)
uart.init(9600, bits=8, parity=None, stop=1, timeout=0, flow=0, timeout_char=0, read_buf_len=512)

pin = pyb.Pin('Y6')

now=time.localtime()
pin.off()
time.sleep(1)
pin.on()
time.sleep(2)
uart.write('\r')  # b'METREC.X Version 4.23 SN:50229\r\nAML Oceanographic Ltd.\r\n942.8 MBytes installed \r\n\r\n'
                  # b'2020-09-22 14:13:54.01  40.754  23.469 -0000.01  0000.10  00.02  00.00  207.7  007.93  1017.715  1521.90 \r\n'
time.sleep(2)
uart.write('\r')  # b'\r\n>'
uart.write('SET SCAN LOGGING\r')  # b'SET SCAN LOGGING\r\n' b'>'
uart.write('\rSET SCAN LOGGING\r')  # b'\r\n>SET SCAN LOGGING\r\n>'
uart.write('DIS DATE\r')  # b'DIS DATE\r\nCurrent date is 2020-09-22\r\n>'
uart.write('SET DATE {:02d}/{:02d}/{:02d}\r'.format(now[1], now[2], int(str(now[0])[:-2])))  # b'SET DATE 09/22/20\r\n>'
while True:
    if uart.any():
        print(uart.read())
