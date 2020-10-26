HOSTNAME = "MAMBO3"
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
    ['gps', ('last_fix'), None, None, None, None, range(5, 60, 10), 0, None],         # every 10 minutes start@5th minute
    ['gps', ('log','last_fix'), None, None, None, range(1, 24), range(0, 60, 10), 0, None], # every 10 minutes from 1am to 11pm
    ['gps', ('log','last_fix','sync_rtc'), None, None, None, 0, 0, 0, None],        # @ midnight
    ['gps', ('log','last_fix'), None, None, None, 0, range(10, 60, 10), 0, None],   # every 10 minutes until from 0 to 1am
    ['meteo', None, None, None, None, None, range(0, 60, 10), 0, None],             # every 10 minutes 1 second after gps
    #['ctd', None, None, None, None, None, range(0, 60, 10), 0, None],               # every 10 minutes 1 second after gps
    #['uv', None, None, None, None, None, range(0, 60, 10), 0, None],                # every 10 minutes
    #['adcp', None, None, None, None, None, range(0, 60, 10), 0, None],              # every 10 minutes (default)
    ['sysmon', None, None, None, None, None, range(0, 60, 10), 0, None]            # every 10 minutes
    #['modem', None, None, None, None, None, 15, 0, None]                      # every hour @ 5th minute
    )
BUF_DAYS = 5
DISPLACEMENT_THRESHOLD = 0.02699784 # Nautical miles: (100meters)
DEBUG = False
VERBOSE = True
