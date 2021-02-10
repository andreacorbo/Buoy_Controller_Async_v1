HOSTNAME = "MAMBO0"
LOG_LEVEL = ("e")   # e, w, m.
LOG_TO_FILE = True  # False screen output, True log to file.
TIMEOUT = 10        # sec.
DEVS = (
    "dev_young.METEO",
    "dev_aml.CTD",
    "dev_aml.UV",
    "dev_nortek.ADCP",
    "dev_gps.GPS"
    )  # Ordered as bob ports.

CRON = (
    #[object, tasks, wday, month, mday, hours, mins, secs, times],
    ['gps', ('last_fix'), None, None, None, None, range(5, 60, 10), 0, None],       # every 10 minutes start@5th minute
    ['gps', ('log','last_fix'), None, None, None, None, range(0, 60, 10), 0, None], # every 10 minutes from 1am to 11pm
    ['gps', 'sync_rtc', None, None, None, 0, 2, 30, None],                          # @ midnight
    ['meteo', None, None, None, None, None, range(0, 60, 10), 0, None],             # every 10 minutes 1 second after gps
    ['ctd', None, None, None, None, None, range(0, 60, 10), 0, None],               # every 10 minutes 1 second after gps
    ['uv', None, None, None, None, None, range(0, 60, 10), 0, None],                # every 10 minutes
    ['adcp', None, None, None, None, None, range(0, 60, 10), 0, None],              # every 10 minutes (default)
    ['sysmon', None, None, None, None, None, range(0, 60, 10), 0, None],            # every 10 minutes
    ['modem', 'datacall', None, None, None, None, range(5, 60, 30), 0, None]             # every 30 minutes @ 5th minute
    )
BUF_DAYS = 5
DISPLACEMENT_THRESHOLD = 0.002699784#0.02699784 # Nautical miles: (50meters)
DEBUG = False
VERBOSE = True
RTC_CALIBRATION = -170
