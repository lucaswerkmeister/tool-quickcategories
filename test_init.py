import datetime
import flask
from pathlib import Path
import pytest

from init import load_config, load_consumer_token, load_database_params

expected_config = {
    'SECRET_KEY': 'secret key',
    'OAUTH': {
        'consumer_key': 'OAuth consumer key',
        'consumer_secret': 'OAuth consumer secret',
    },
    'EDITGROUPS': {
        'commonswiki': {
            'domain': 'commons.wikimedia.org',
            'url': 'https://editgroups-commons.toolforge.org/b/QC/{0}/',
            'since': datetime.datetime(2021, 9, 14, tzinfo=datetime.timezone.utc),
        },
    },
}

def test_load_config_file(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
SECRET_KEY: 'secret key'
OAUTH:
    consumer_key: 'OAuth consumer key'
    consumer_secret: 'OAuth consumer secret'
EDITGROUPS:
    commonswiki:
        domain: commons.wikimedia.org
        url: "https://editgroups-commons.toolforge.org/b/QC/{0}/"
        since: 2021-09-14T00:00:00Z
# READ_ONLY_REASON: 'commented out'
""".strip(), encoding="utf-8")
    # note: chmod *after* writing the file is unsafe,
    # don’t do this outside of a unit test ;)
    config_file.chmod(0o600)
    config = flask.Config(root_path=tmp_path)
    load_config(config)
    assert config == expected_config

def test_load_config_file_otherreadable(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("SECRET_KEY: 'not so secret key'", encoding="utf-8")
    # no chmod
    config = flask.Config(root_path=tmp_path)
    with pytest.raises(ValueError, match='should be private'):
        load_config(config)

def test_load_config_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv('TOOL_SECRET_KEY', 'secret key')
    monkeypatch.setenv('TOOL_OAUTH__CONSUMER_KEY', 'OAuth consumer key')
    monkeypatch.setenv('TOOL_OAUTH__CONSUMER_SECRET', 'OAuth consumer secret')
    monkeypatch.setenv('TOOL_EDITGROUPS__COMMONSWIKI__DOMAIN',
                       'commons.wikimedia.org')
    monkeypatch.setenv('TOOL_EDITGROUPS__COMMONSWIKI__URL',
                       'https://editgroups-commons.toolforge.org/b/QC/{0}/')
    monkeypatch.setenv('TOOL_EDITGROUPS__COMMONSWIKI__SINCE',
                       '2021-09-14T00:00:00Z')
    config = flask.Config(root_path=tmp_path)
    load_config(config)
    assert config == expected_config

def test_load_config_both(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
# SECRET_KEY: 'moved to env'
OAUTH:
    consumer_key: 'OAuth consumer key'
    # consumer_secret: 'moved to env'
EDITGROUPS:
    commonswiki:
        domain: commons.wikimedia.org
        url: "https://editgroups-commons.toolforge.org/b/QC/{0}/"
        since: 2021-09-14T00:00:00Z
# READ_ONLY_REASON: 'commented out'
""".strip(), encoding="utf-8")
    # note: chmod *after* writing the file is unsafe,
    # don’t do this outside of a unit test ;)
    config_file.chmod(0o600)
    monkeypatch.setenv('TOOL_SECRET_KEY', 'secret key')
    monkeypatch.setenv('TOOL_OAUTH__CONSUMER_SECRET', 'OAuth consumer secret')
    config = flask.Config(root_path=tmp_path)
    load_config(config)
    assert config == expected_config

def test_load_consumer_token_configured(tmp_path: Path) -> None:
    config = flask.Config(root_path=tmp_path, defaults={
        'OAUTH': {
            'consumer_key': 'OAuth consumer key',
            'consumer_secret': 'OAuth consumer secret',
        },
    })
    consumer_token = load_consumer_token(config)
    assert consumer_token is not None
    assert consumer_token.key == 'OAuth consumer key'
    assert consumer_token.secret == 'OAuth consumer secret'

def test_load_consumer_token_unconfigured(tmp_path: Path) -> None:
    config = flask.Config(root_path=tmp_path)
    consumer_token = load_consumer_token(config)
    assert consumer_token is None

def test_load_database_params_localhost(tmp_path: Path) -> None:
    config = flask.Config(root_path=tmp_path, defaults={
        'DATABASE': {
            'user': 'test user',
            'password': 'test password',
            'db': 'test database',
        },
    })
    database_params = load_database_params(config)
    assert database_params == {
        'user': 'test user',
        'password': 'test password',
        'db': 'test database',
    }

def test_load_database_params_toolsdb(tmp_path: Path) -> None:
    config = flask.Config(root_path=tmp_path, defaults={
        'TOOLSDB_USER': 's53976',
        'TOOLSDB_PASSWORD': 'test password',
        'DATABASE': {
            'toolsdb': True,
            'db': 's53976__quickcategories',
        },
    })
    database_params = load_database_params(config)
    assert database_params == {
        'db': 's53976__quickcategories',
        'host': 'tools.db.svc.wikimedia.cloud',
        'user': 's53976',
        'password': 'test password',
    }

def test_load_database_params_unconfigured(tmp_path: Path) -> None:
    config = flask.Config(root_path=tmp_path)
    database_params = load_database_params(config)
    assert database_params is None
