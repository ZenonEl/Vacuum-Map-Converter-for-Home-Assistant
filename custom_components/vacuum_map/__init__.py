"""Vacuum Map Converter for Home Assistant."""
import os
import logging
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_PATH, CONF_SCAN_INTERVAL
import homeassistant.helpers.entity_component as entity_component
from datetime import timedelta

from .const import (
    DOMAIN,
    CONF_MAP_PATH,
    DEFAULT_MAP_PATH,
    DEFAULT_SCAN_INTERVAL,
    SERVICE_CONVERT_MAP,
    ATTR_OUTPUT_PATH,
)
from .map_converter import create_map_image

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=300)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_MAP_PATH, default=DEFAULT_MAP_PATH): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

CONVERT_MAP_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MAP_PATH): cv.string,
        vol.Optional(ATTR_OUTPUT_PATH): cv.string,
    }
)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Vacuum Map Converter component."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    hass.data[DOMAIN] = {
        CONF_MAP_PATH: conf[CONF_MAP_PATH],
        CONF_SCAN_INTERVAL: conf[CONF_SCAN_INTERVAL],
    }

    async def handle_convert_map(call: ServiceCall) -> None:
        """Handle the convert_map service call."""
        map_path = call.data.get(CONF_MAP_PATH, hass.data[DOMAIN][CONF_MAP_PATH])
        output_path = call.data.get(ATTR_OUTPUT_PATH, os.path.join(map_path, "vacuum_map_ha.png"))
        
        # Check if map directory exists
        if not os.path.isdir(map_path):
            _LOGGER.error("Map directory does not exist: %s", map_path)
            return
            
        # Required files for conversion
        required_files = ['map_record.map', 'map_record.json', 'charger_pose.json', 'area_info.json']
        missing_files = [f for f in required_files if not os.path.exists(os.path.join(map_path, f))]
        
        if missing_files:
            _LOGGER.error("Missing required map files: %s", ", ".join(missing_files))
            return
            
        try:
            # Run conversion in executor
            await hass.async_add_executor_job(
                create_map_image,
                map_path,
                output_path
            )
            _LOGGER.info("Successfully converted vacuum map to: %s", output_path)
        except Exception as ex:
            _LOGGER.error("Error converting vacuum map: %s", ex)

    # Register service
    hass.services.async_register(
        DOMAIN, SERVICE_CONVERT_MAP, handle_convert_map, schema=CONVERT_MAP_SCHEMA
    )

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Vacuum Map Converter from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Store configuration
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_MAP_PATH: entry.options.get(CONF_MAP_PATH, DEFAULT_MAP_PATH),
        CONF_SCAN_INTERVAL: entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    }
    
    # Initialize services if not already done
    if not hass.services.has_service(DOMAIN, SERVICE_CONVERT_MAP):
        await async_setup(hass, {DOMAIN: hass.data[DOMAIN][entry.entry_id]})
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    if not hass.data[DOMAIN]:
        # If this is the last config entry, unregister services
        if hass.services.has_service(DOMAIN, SERVICE_CONVERT_MAP):
            hass.services.async_remove(DOMAIN, SERVICE_CONVERT_MAP)
    
    return True