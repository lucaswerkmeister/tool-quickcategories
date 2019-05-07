import datetime


def now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc).replace(microsecond=0)

def datetime_to_utc_timestamp(dt: datetime.datetime) -> int:
    assert dt.tzinfo == datetime.timezone.utc
    assert dt.microsecond == 0
    return int(dt.timestamp())

def utc_timestamp_to_datetime(timestamp: int) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(timestamp,
                                           tz=datetime.timezone.utc)
