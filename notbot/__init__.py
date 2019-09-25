import os
import sys
import configparser
import logging.config

# import yaml
import json
import discord
import logging
from discord.ext import commands
from .context import Context

from .notbot import NOTBOT
from .cogs.raid import RaidModule
from .cogs.info import InfoModule
from .cogs.admin import AdminModule
from .cogs.efficiency import EfficiencyModule
from .cogs.restriction import RestrictionModule


def apply_overwrite(node: dict, key, value):
    if isinstance(value, dict):
        v = node.get(key)
        if not v:
            node[key] = value
        else:
            for item in value:
                apply_overwrite(node[key], item, value[item])
    else:
        node[key] = value


def setup_logging():
    log_config_path = "logging-default.json"
    log_config_overwrite_path = "logging.json"
    c = None
    if os.path.exists(log_config_path):
        with open(log_config_path, "rt") as f:
            c = json.load(f)

    if os.path.exists(log_config_overwrite_path):
        with open(log_config_overwrite_path, "rt") as f:
            if not c:
                c = json.load(f)
            else:
                overwrite_values = json.load(f)
                for overwrite_key, value in overwrite_values.items():
                    apply_overwrite(c, overwrite_key, value)

    if c:
        logging.config.dictConfig(c)
    else:
        logging.basicConfig(level="INFO")


# def get_config(configuration_file: str = "default_config.ini"):
#     config = configparser.ConfigParser()
#     config.read("default_config.ini")
#     if configuration_file != "default_config.ini":
#         config.read(configuration_file)
#     return config


setup_logging()

context = (
    Context()
    .with_module(RaidModule)
    .with_module(InfoModule)
    .with_module(AdminModule)
    .with_module(EfficiencyModule)
    .with_module(RestrictionModule)
)

# context.start()
# bot = NOTBOT(ctx=context)
