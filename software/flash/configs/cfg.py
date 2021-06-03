HOSTNAME = "MAMBO0"
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
    ['gps', ('follow_me'), None, None, None, None, range(5, 60, 10), 0, None],       # every 10 minutes start@5th minute
    ['gps', ('log','last_fix'), None, None, None, None, range(0, 60, 10), 0, None], # every 10 minutes from 1am to 11pm
    ['gps', 'sync_rtc', None, None, None, 0, 2, 30, None],                          # @ midnight
    ['meteo', None, None, None, None, None, range(0, 60, 10), 1, None],             # every 10 minutes 1 second after gps
    ['ctd', None, None, None, None, None, range(0, 60, 10), 1, None],               # every 10 minutes 1 second after gps
    ['uv', None, None, None, None, None, range(5, 60, 10), 0, None],                # every 10 minutes
    ['adcp', None, None, None, None, None, range(0, 60, 10), 0, None],              # every 10 minutes (default)
    ['sysmon', None, None, None, None, None, range(0, 60, 10), 0, None],            # every 10 minutes
    ['modem', 'datacall', None, None, None, range(0, 23), 20, 0, None]        # every 30 minutes @ 5th minute
    )
BUF_DAYS = 4
DISPLACEMENT_THRESHOLD = 0.05399568 # Nautical miles: (50meters)
DEBUG = False
VERBOSE = False
RTC_CALIBRATION = -170
SMS_RECIPIENTS = ['+393664259612','+393664259612']
