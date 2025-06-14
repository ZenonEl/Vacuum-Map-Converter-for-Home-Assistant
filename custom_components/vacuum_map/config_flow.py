"""Configuration flow for Vacuum Map Converter integration."""
import os
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_PATH, CONF_SCAN_INTERVAL

from .const import (
    DOMAIN,
    CONF_MAP_PATH,
    DEFAULT_MAP_PATH,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

class VacuumMapConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vacuum Map Converter."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            map_path = user_input[CONF_MAP_PATH]
            
            # Validate that the map path exists
            if not await self.hass.async_add_executor_job(os.path.isdir, map_path):
                errors[CONF_MAP_PATH] = "directory_not_found"
            else:
                # Check for required map files
                required_files = ['map_record.map', 'map_record.json', 'charger_pose.json', 'area_info.json']
                missing_files = []
                
                for file in required_files:
                    file_path = os.path.join(map_path, file)
                    if not await self.hass.async_add_executor_job(os.path.isfile, file_path):
                        missing_files.append(file)
                
                if missing_files:
                    errors[CONF_MAP_PATH] = "missing_files"
                    _LOGGER.error("Missing required files in map directory: %s", ", ".join(missing_files))
                else:
                    # Valid configuration
                    return self.async_create_entry(
                        title="Vacuum Map Converter",
                        data={},
                        options={
                            CONF_MAP_PATH: map_path,
                            CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                        },
                    )

        # Show form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MAP_PATH, default=DEFAULT_MAP_PATH): str,
                    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return VacuumMapOptionsFlow(config_entry)


class VacuumMapOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Vacuum Map Converter."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}

        if user_input is not None:
            map_path = user_input[CONF_MAP_PATH]
            
            # Validate that the map path exists
            if not await self.hass.async_add_executor_job(os.path.isdir, map_path):
                errors[CONF_MAP_PATH] = "directory_not_found"
            else:
                # Check for required map files
                required_files = ['map_record.map', 'map_record.json', 'charger_pose.json', 'area_info.json']
                missing_files = []
                
                for file in required_files:
                    file_path = os.path.join(map_path, file)
                    if not await self.hass.async_add_executor_job(os.path.isfile, file_path):
                        missing_files.append(file)
                
                if missing_files:
                    errors[CONF_MAP_PATH] = "missing_files"
                    _LOGGER.error("Missing required files in map directory: %s", ", ".join(missing_files))
                else:
                    # Valid configuration
                    return self.async_create_entry(
                        title="",
                        data={
                            CONF_MAP_PATH: map_path,
                            CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                        },
                    )

        options = {
            vol.Required(
                CONF_MAP_PATH,
                default=self.config_entry.options.get(CONF_MAP_PATH, DEFAULT_MAP_PATH),
            ): str,
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): int,
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(options),
            errors=errors,
        )