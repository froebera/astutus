from typing import List
import configparser
from ..context import Context, Module
import logging

logger = logging.getLogger(__name__)
MODULE_NAME = "config_service"


class ConfigService(Module):
    def __init__(self, context: Context):
        self.config: configparser.ConfigParser

    def get_name(self):
        return MODULE_NAME

    def start(self):
        self.config = self._read_config("config.ini")
        logger.debug("Configuration:")
        for section in self.config.sections():
            logger.debug("[%s]", section)
            for (key, value) in self.config.items(section):
                logger.debug("  %s: %s", key, self._mask_config_value(key, value))

    def _read_config(self, configuration_file: str = "default_config.ini"):
        config = configparser.ConfigParser()
        config.read("default_config.ini")
        if configuration_file != "default_config.ini":
            config.read(configuration_file)
        return config

    def _mask_config_value(self, config_key: str, config_value: str) -> str:
        to_mask = ["password", "pw", "pwd", "token"]
        if config_key in to_mask:
            return "*******"
        return config_value

    def get_config(self, config_name):
        return self.config[config_name]


def get_config_service(context: Context) -> ConfigService:
    return context.get_or_register_module(MODULE_NAME, lambda: ConfigService(context))
