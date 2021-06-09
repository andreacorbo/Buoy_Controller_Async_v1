HOSTNAME = "MAMBO3"
LOG_LEVEL = ("e")   # e, w, m.
LOG_TO_FILE = True  # False screen output, True log to file.
TIMEOUT = 10        # sec.
DEVS = (
    "dev_young.METEO",
    "dev_aml.CTD",
    "dev_aml.UV",
    "dev_nortek.ADCP",
    None,
    "dev_gps.GPS"
    )  # Ordered as bob ports

CRON = (
    #[object, tasks, wday, month, mday, hours, mins, secs, times],
    ['gps', ('follow_me'), None, None, None, None, range(5, 60, 10), 0, None],      # every 10 minutes start@5th minute
    ['gps', ('log','last_fix'), None, None, None, None, range(0, 60, 10), 0, None], # every 10 minutes start@0 minute
    ['gps', 'sync_rtc', None, None, None, 0, 2, 30, None],                          # @ 00:02:30
    ['meteo', None, None, None, None, None, range(0, 60, 10), 2, None],             # every 10 minutes 2 second after gps
    ['ctd', None, None, None, None, None, range(0, 60, 10), 2, None],               # every 10 minutes 2 second after gps
    ['uv', None, None, None, None, None, range(5, 60, 10), 0, None],                # every 10 minutes
    ['adcp', None, None, None, None, None, range(0, 60, 10), 0, None],              # every 10 minutes (default)
    ['sysmon', None, None, None, None, None, range(0, 60, 10), 0, None],            # every 10 minutes
    ['modem', 'datacall', None, None, None, None, range(12, 60, 30), 0, None]       # every 30 minutes start@12th minute
    )
BUF_DAYS = 4
DISPLACEMENT_THRESHOLD = 0.054 # Nautical miles: (100 m)
DEBUG = False
VERBOSE = False
RTC_CALIBRATION = -170
SMS_RECIPIENTS = ['+393664259612','+393664259612']  # SOR '+393351079053' 
