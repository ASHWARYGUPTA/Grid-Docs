import math
from datetime import datetime
from zoneinfo import ZoneInfo

from grid_unlocked.features.constants import IST, PEAK_HOURS

UTC = ZoneInfo("UTC")


def to_ist(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC).astimezone(IST)
    return dt.astimezone(IST)


def cyclical_temporal(start: datetime) -> dict:
    t = to_ist(start)
    hour = t.hour
    dow = t.weekday()
    two_pi = 2.0 * math.pi

    return {
        "hour_ist": hour,
        "dow": dow,
        "hour_sin": math.sin(two_pi * hour / 24.0),
        "hour_cos": math.cos(two_pi * hour / 24.0),
        "dow_sin": math.sin(two_pi * dow / 7.0),
        "dow_cos": math.cos(two_pi * dow / 7.0),
        "is_peak_hour": hour in PEAK_HOURS,
        "is_weekend": dow >= 5,
    }
