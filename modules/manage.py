try:
    import uvloop

    uvloop.install()
except ImportError:
    print("No uvloop installed.")

import configparser
import sys
import asyncio

from bot import AstutusBot
from modules.utils.setup import setup_bot


def get_config(configuration_file: str = "default_config.ini"):
    config = configparser.ConfigParser()
    config.read("default_config.ini")
    if configuration_file != "default_config.ini":
        config.read(configuration_file)
    return config


def get_event_loop():
    try:
        import uvloop
    except ImportError:
        pass
    else:
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    return asyncio.get_event_loop()


def run_bot(configuration_file):
    bot = AstutusBot(config=configuration_file)
    setup_bot(bot)
    bot.run()


def main():
    cfg = get_config("config.ini")
    while True:
        try:
            run_bot(cfg)
        except (KeyboardInterrupt, RuntimeError):
            sys.exit(1)


if __name__ == "__main__":
    main()
