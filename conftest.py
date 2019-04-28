import freezegun # type: ignore
import pytest # type: ignore


@pytest.fixture
def frozen_time():
    with freezegun.freeze_time() as frozen_time:
        yield frozen_time
