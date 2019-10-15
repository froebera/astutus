import logging
import humanfriendly

logger = logging.getLogger(__name__)


def num_to_hum(num):
    num = humanfriendly.format_number(round(num))
    nmap = "K M B T".split()
    commas = num.count(",")
    points = num.split(",")
    if not commas:
        return num

    human_friendly_num = f"{points[0]}.{points[1]}{nmap[commas-1]}"

    logger.debug("Formatted %s to %s", num, human_friendly_num)

    return human_friendly_num


def success_message(message: str):
    return ":white_check_mark: {}".format(message)
