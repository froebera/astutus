import logging
import math
from decimal import Decimal

logger = logging.getLogger(__name__)


def _remove_exponent(d):
    return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()


def num_to_hum(num):
    nmap = ["", "k", "M", "B", "T", "P", "E", "Z", "Y"]
    num = float(num)
    idx = max(
        0,
        min(
            len(nmap) - 1, int(math.floor(0 if num == 0 else math.log10(abs(num)) / 3))
        ),
    )
    result = "{:.{precision}f}".format(num / 10 ** (3 * idx), precision=3)
    result = _remove_exponent(Decimal(result))
    formatted_result = "{0}{dx}".format(result, dx=nmap[idx])
    logger.debug("Formatted %s to %s", num, formatted_result)
    return formatted_result


def success_message(message: str):
    return ":white_check_mark: {}".format(message)
