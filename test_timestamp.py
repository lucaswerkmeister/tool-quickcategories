import datetime
import pytest

from timestamp import datetime_to_utc_timestamp, utc_timestamp_to_datetime


def test_datetime_to_utc_timestamp() -> None:
    dt = datetime.datetime(2019, 3, 17, 13, 23, 28, tzinfo=datetime.timezone.utc)
    assert datetime_to_utc_timestamp(dt) == 1552829008

@pytest.mark.parametrize('dt', [
    datetime.datetime.now(),
    datetime.datetime.utcnow(),
    datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=1))),
    datetime.datetime(2019, 3, 17, 13, 23, 28, 251638, tzinfo=datetime.timezone.utc)
])
def test_datetime_to_utc_timestamp_invalid_timezone(dt: datetime.datetime) -> None:
    with pytest.raises(AssertionError):
        datetime_to_utc_timestamp(dt)

def test_utc_timestamp_to_datetime() -> None:
    dt = datetime.datetime(2019, 3, 17, 13, 23, 28, tzinfo=datetime.timezone.utc)
    assert utc_timestamp_to_datetime(1552829008) == dt
