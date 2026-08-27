import asyncio
import logging
import os
from typing import Any

import yaml
from homeassistant.core import HomeAssistant

from ..const import INTEGRATION_NAME

__LOGGER__ = logging.getLogger(__name__)


class ApplicationProfile:
    __active: str = ""
    __configFile: str = ""
    __configPath: str = ""

    def __init__(self, active: str | None = None) -> None:
        self.config: dict[str, Any] = {}
        self.__active = active or os.getenv("BLUETTI_PROFILE_ACTIVE", "").lower()
        __LOGGER__.info("Setting up application profile: %s", "prod" if self.__active == "" else self.__active)

        if self.__active != "":
            self.__active = "-" + self.__active

        self.__configFile = "application" + self.__active + ".yaml"
        self.__configPath = os.path.dirname(os.path.abspath(__file__)) + "/" + self.__configFile

    """加载运行环境的配置文件"""
    def load_config(self, hass: HomeAssistant) -> asyncio.Future[None]:
        return hass.async_add_executor_job(self.__load_config)

    def __load_config(self) -> None:
        try:
            with open(self.__configPath) as file:
                __yaml__ = yaml.safe_load(file)
        except (OSError, yaml.YAMLError) as err:
            __LOGGER__.error(
                "Failed to load profile %s of `%s` integration: %s",
                self.__configFile, INTEGRATION_NAME, err,
            )
            raise

        __LOGGER__.info("Load profile " f"{self.__configFile} of `{INTEGRATION_NAME}` integration successfully.")
        self.config = __yaml__["bluetti"]


# The application profile. Was previously defined in api/bluetti.py, which
# moved to the pybluetti package; relocated here since this is where the
# class it instantiates lives.
APPLICATION_PROFILE = ApplicationProfile()
