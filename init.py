import flask
import mwoauth  # type: ignore
import toolforge
from typing import Any, Optional
import yaml


user_agent = toolforge.set_user_agent('quickcategories', email='mail@lucaswerkmeister.de')


def _lowercase_dict(d: Any) -> Any:
    if not isinstance(d, dict):
        return d
    lowercased = {k.lower(): _lowercase_dict(v) for k, v in d.items()}
    assert len(d) == len(lowercased), \
        f'conflicting keys when lowercasing all the keys in {d}'
    return lowercased


def load_config(config: flask.Config) -> bool:
    """Populate the given config from the configuration sources."""
    initial_config = dict(config)
    config.from_file('config.yaml',
                     load=toolforge.load_private_yaml,
                     silent=True)
    config.from_prefixed_env('TOOL',
                             loads=yaml.safe_load)
    # lowercase all keys in nested dicts to work around T374780
    for k, v in config.items():
        config[k] = _lowercase_dict(v)
    has_config = initial_config != config
    return has_config


def load_consumer_token(config: flask.Config) -> Optional[mwoauth.ConsumerToken]:
    """Load the OAuth consumer token from the given config."""
    try:
        return mwoauth.ConsumerToken(config['OAUTH']['consumer_key'], config['OAUTH']['consumer_secret'])
    except KeyError:
        return None


def load_database_params(config: flask.Config) -> Optional[dict]:
    """Load the database connection_params from the given config."""
    try:
        connection_params = config['DATABASE']
    except KeyError:
        return None
    connection_params = dict(connection_params)
    if connection_params.pop('toolsdb', False):
        connection_params.setdefault('host', 'tools.db.svc.wikimedia.cloud')
        connection_params.setdefault('user', config['TOOLSDB_USER'])
        connection_params.setdefault('password', config['TOOLSDB_PASSWORD'])
    return connection_params
