"""Constants for the Garnet Panel integration."""

DOMAIN = "garnet_home_assistant"

DEFAULT_KEEPALIVE_INTERVAL = 60
MIN_KEEPALIVE_INTERVAL = 60
CONF_KEEPALIVE_INTERVAL = "conf_keepalive"

CONF_ACCOUNT = "conf_clientid"
CONF_SYSTEM = "conf_systemid"
CONF_GARNETUSER = "conf_username"
CONF_GARNETPASS = "conf_password"


DEFAULT_UDP_PORT = 2123
SIA_BUFFERSIZE = 1024
MESSAGESERVER_TIMEOUT = 30
GARNETAPIURL = "web.garnetcontrol.app"
GARNETAPITIMEOUT = 8500     #TODO obtenerlo de la API

PARTITION_BASE_ID = 0
ZONE_BASE_ID = 10
HOWLER_BASE_ID = 50
FIREBUTTON_BASE_ID = 51
DOCTORBUTTON_BASE_ID = 52
POLICEBUTTON_BASE_ID = 53
TIMEDPANICBUTTON_BASE_ID = 54
COMM_BASE_ID = 55
REFRESHBUTTON_BASE_ID = 56

TOKEN_TIME_SPAN = 600