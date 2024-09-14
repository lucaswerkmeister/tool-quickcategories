import decorator
import flask
import mwoauth  # type: ignore
import os
import stat
import toolforge
from typing import Any, Callable, Optional
import yaml


user_agent = toolforge.set_user_agent('quickcategories', email='mail@lucaswerkmeister.de')


@decorator.decorator
def read_private(func: Callable, *args: Any, **kwargs: Any) -> Any:
    try:
        f = args[0]
        fd = f.fileno()
    except AttributeError:
        pass
    except IndexError:
        pass
    else:
        mode = os.stat(fd).st_mode
        if (stat.S_IRGRP | stat.S_IROTH) & mode:
            name = getattr(f, "name", "config file")
            raise ValueError(f'{name} is readable to others, '
                             'must be exclusively user-readable!')
    return func(*args, **kwargs)


def load_config(config: flask.Config) -> bool:
    """Populate the given config from the configuration sources."""
    has_config = config.from_file('config.yaml',
                                  load=read_private(yaml.safe_load),
                                  silent=True)
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
        return config['DATABASE']
    except KeyError:
        return None
