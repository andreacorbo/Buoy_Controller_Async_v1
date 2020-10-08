import time

HOSTNAME = "MAMBO2"
LOG_LEVEL = ("e")   # e, w, m.
LOG_TO_FILE = True  # False screen output, True log to file.
TIMEOUT = 10        # sec.
DEVS = (
    "dev_young.METEO",
    "dev_aml.CTD",
    "dev_aml.UV",
    "dev_nortek.ADCP",
    None
    )  # Ordered as bob ports.

CRON = (
    #[object, task_list, lock, wday, month, mday, hours, mins, secs, times],
    ['gps', ['last_fix'], 'f_lock', None, None, None, None, range(5, 60, 10), 0, None],            # every 10' start @ 5'
    ['gps', ['log','last_fix'], 'f_lock', None, None, None, None, range(0, 60, 10), 0, None],      # every 10' start @ 0'
    ['meteo', ['log'], 'f_lock', None, None, None, None, range(0, 60, 10), 1, None],               # every 10' start @ 0' 1''
    ['ctd', ['log'], 'f_lock', None, None, None, None, range(0, 60, 10), 0, None],                 # every 10' start @ 0'
    ['uv', None, None, None, None, None, None, range(0, 60, 10), 0, None],                          # every 10' start @ 0'
    ['adcp', ['log'], 'f_lock', None, None, None, None, range(0, 60, 10), 0, None],                # every 10' start @ 0'
    ['sysmon', ['log'], 'f_lock', None, None, None, None, range(0, 60, 10), 0, None],              # every 10' start @ 0'
    )
DATA_FILE = "{:04d}{:02d}{:02d}".format(time.localtime()[0], time.localtime()[1], time.localtime()[2])
BUF_DAYS = 5
DISPLACEMENT_THRESHOLD = 0.05399568 # Nautical miles: (100meters)
DEBUG = False
VERBOSE = True
