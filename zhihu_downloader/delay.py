import random
import time
from typing import Tuple


def random_sleep(delay_range: Tuple[float, float]) -> None:
    min_delay, max_delay = delay_range
    time.sleep(random.uniform(min_delay, max_delay))


def describe_delay_range(delay_range: Tuple[float, float]) -> str:
    min_delay, max_delay = delay_range
    if min_delay == max_delay:
        return f"{min_delay:g} 秒"
    return f"{min_delay:g}-{max_delay:g} 秒随机"

