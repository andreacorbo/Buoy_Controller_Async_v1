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
    ['gps', ('log','last_fix'), None, None, None, None, range(0, 60, 10), 0, None], # every 10 minutes
    ['gps', 'sync_rtc', None, None, None, 13, 2, 30, None],                          # @ 00:02:30
    ['meteo', None, None, None, None, None, range(0, 60, 10), 1, None],                   # every 10 minutes @ 1st second
    ['ctd', None, None, None, None, None, range(0, 60, 10), 0, None],                     # every 10 minutes
    ['uv', None, None, None, None, None, range(0, 60, 10), 0, None],          # every 10 minutes
    ['adcp', None, None, None, None, None, None, 0, None],                    # every 10 minutes (default)
    ['sysmon', None, None, None, None, None, range(0, 60, 10), 0, None],                  # every 10 minutes
    ['modem', None, None, None, None, None, range(0,60,30), 0, None]                     # every hour @ 5th minute
    )
BUF_DAYS = 5
DISPLACEMENT_THRESHOLD = 0.0001#0.05399568 # Nautical miles: (100meters)
DEBUG = False
VERBOSE = False
