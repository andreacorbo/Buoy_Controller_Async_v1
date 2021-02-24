SW_NAME = "BUOY_CONTROLLER_ASYNC"
SW_VERSION = "v1"
RESET_CAUSE = ("SOFT_RESET","PWRON_RESET","HARD_RESET","WDT_RESET","DEEPSLEEP_RESET")
CONFIG_DIR = "configs/"
CONFIG_TYPE = ".json"
LOG_DIR = "/sd/log"
LOG_FILE = "syslog"
LOG_LINES = 50
ESC_CHAR = "#"
PASSWD = "ogsp4lme"
LOGIN_ATTEMPTS = 3
SESSION_TIMEOUT = 120   # sec.
DEVS = (
    None,
    None,
    None,
    None,
    None,
    "dev_modem.MODEM",
    "dev_board.SYSMON"
    )  # Ordered as bob ports
UARTS = (
    2,
    4,
    None,
    6,
    1,
    3
    )    # Ordered as bob ports.
CTRL_PINS = (
    "X12",
    "Y6",
    "Y4",
    "Y3",
    #"X11",
    "Y7",
    "Y5"
    )    # Ordered as bob ports.
WD_TIMEOUT = 30000  # 1000ms < watchdog timer timeout < 32000ms
DATA_DIR = "/sd/data"
BKP_FILE_PFX = "."
TMP_FILE_PFX = "$"
SENT_FILE_PFX = "#"
DATA_SEPARATOR = ","
STATUS = ("off","on","run_until_expire","run_until_complete")
