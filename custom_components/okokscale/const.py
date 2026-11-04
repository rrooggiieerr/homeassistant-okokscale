"""Constants for the OKOK Scale integration."""

DOMAIN = "okokscale"

# The OKOK Scale integration in Home Assistant Core, which takes over from this
# integration. Config entries, devices and entities are migrated to it.
CORE_DOMAIN = "okok_scale"
# First Home Assistant version (major, minor) that has the Core integration
CORE_SINCE = (2026, 11)
# Version of the config entries that Core creates, see
# homeassistant/components/okok_scale/config_flow.py. Core doesn't set a minor
# version, so it uses the default of 1.
CORE_VERSION = 1
CORE_MINOR_VERSION = 1
