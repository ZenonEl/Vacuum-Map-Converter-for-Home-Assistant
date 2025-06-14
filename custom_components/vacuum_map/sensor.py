"""Vacuum Map Sensor component for Home Assistant."""
import os
import logging
from datetime import timedelta
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import (
    DOMAIN,
    CONF_MAP_PATH,
    DEFAULT_MAP_PATH,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)
from .map_converter import create_map_image

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default="Vacuum Map"): cv.string,
    vol.Optional(CONF_MAP_PATH, default=DEFAULT_MAP_PATH): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.positive_int,
})

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Vacuum Map Sensor platform."""
    name = config.get(CONF_NAME)
    map_path = config.get(CONF_MAP_PATH)
    scan_interval = config.get(CONF_SCAN_INTERVAL)
    
    sensor = VacuumMapSensor(hass, name, map_path, scan_interval)
    async_add_entities([sensor], True)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Vacuum Map Sensor from a config entry."""
    map_path = config_entry.options.get(CONF_MAP_PATH, DEFAULT_MAP_PATH)
    scan_interval = config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    
    sensor = VacuumMapSensor(hass, "Vacuum Map", map_path, scan_interval)
    async_add_entities([sensor], True)

class VacuumMapSensor(SensorEntity):
    """Representation of a Vacuum Map Sensor."""

    def __init__(self, hass, name, map_path, scan_interval):
        """Initialize the sensor."""
        self.hass = hass
        self._name = name
        self._map_path = map_path
        self._output_path = os.path.join(self.hass.config.path("www"), "vacuum_map_ha.png")
        self._state = None
        self._available = False
        self._attr_unique_id = f"{DOMAIN}_{map_path.replace('/', '_')}"
        
        # Set up update method
        self.update = Throttle(timedelta(seconds=scan_interval))(self._update)
        
    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name
        
    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state
        
    @property
    def available(self):
        """Return True if entity is available."""
        return self._available
        
    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "map_path": self._map_path,
            "output_path": self._output_path,
            "image_url": f"/local/{os.path.basename(self._output_path)}"
        }
        
    def _update(self):
        """Update the sensor state."""
        # Check if map directory exists
        if not os.path.isdir(self._map_path):
            _LOGGER.error("Map directory does not exist: %s", self._map_path)
            self._available = False
            return
            
        # Required files for conversion
        required_files = ['map_record.map', 'map_record.json', 'charger_pose.json', 'area_info.json']
        missing_files = [f for f in required_files if not os.path.exists(os.path.join(self._map_path, f))]
        
        if missing_files:
            _LOGGER.error("Missing required map files: %s", ", ".join(missing_files))
            self._available = False
            return
            
        try:
            # Run conversion
            success = create_map_image(self._map_path, self._output_path)
            
            if success:
                self._state = "OK"
                self._available = True
                _LOGGER.info("Successfully updated vacuum map")
            else:
                self._state = "ERROR"
                self._available = True
                _LOGGER.error("Failed to update vacuum map")
        except Exception as ex:
            self._state = "ERROR"
            self._available = False
            _LOGGER.error("Error updating vacuum map: %s", ex)