"""Constants for the Vacuum Map Converter integration."""

DOMAIN = "vacuum_map"

# Configuration
CONF_MAP_PATH = "map_path"
DEFAULT_MAP_PATH = "/config/vacuum_map"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 300  # 5 minutes

# Services
SERVICE_CONVERT_MAP = "convert_map"

# Attributes
ATTR_OUTPUT_PATH = "output_path"

# Entity
ENTITY_ID_FORMAT = DOMAIN + ".{}"