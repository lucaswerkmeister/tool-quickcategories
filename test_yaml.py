import pytest
import yaml

@pytest.mark.parametrize('path', [
    'toolforge.yaml',
    '.gitlab-ci.yml',
])
def test_toolforge_yaml(path: str) -> None:
    with open(path) as f:
        yaml.safe_load(f)
