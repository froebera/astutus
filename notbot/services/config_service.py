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

    def _read_config(self, configuration_file: str = "default_config.ini"):
        config = configparser.ConfigParser()
        config.read("default_config.ini")
        if configuration_file != "default_config.ini":
            config.read(configuration_file)
        return config

    def get_config(self, config_name):
        return self.config[config_name]


def get_config_service(context: Context) -> ConfigService:
    return context.get_or_register_module(MODULE_NAME, lambda: ConfigService(context))
