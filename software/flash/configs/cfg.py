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
    #[object, tasks, wday, month, mday, hours, mins, secs, times],
    ['gps', 'last_fix', None, None, None, None, range(5, 60, 10), 0, None],         # every 10 minutes start@5th minute
    ['gps', ('log','last_fix'), None, None, None, None, range(10, 60, 10), 0, None],# every 10 minutes
    ['gps', ('log','last_fix','sync_rtc'), None, None, None, 1, 0, 0, None],        # @ 00:00:00
    ['meteo', None, None, None, None, None, range(0, 60, 10), 0, None],             # every 10 minutes
    ['ctd', None, None, None, None, None, range(0, 60, 10), 0, None],               # every 10 minutes
    ['uv', None, None, None, None, None, range(0, 60, 10), 0, None],                # every 10 minutes
    ['adcp', None, None, None, None, None, range(0, 60, 10), 0, None],              # every 10 minutes (default)
    ['sysmon', None, None, None, None, None, range(0, 60, 10), 0, None],            # every 10 minutes
    ['modem', None, None, None, None, None, 5, 0, None]                      # every hour @ 5th minute
    )
BUF_DAYS = 5
DISPLACEMENT_THRESHOLD = 0.02699784 # Nautical miles: (100meters)
DEBUG = False
VERBOSE = True
