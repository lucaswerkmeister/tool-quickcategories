#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import flask
import os
import sys

from database import DatabaseBatchStore
from init import load_config, load_database_params


config = flask.Config(os.path.dirname(__file__))
has_config = load_config(config)

database_params = load_database_params(config)
if database_params is None:
    print('No database configuration, cannot run in background')
    sys.exit(1)
batch_store = DatabaseBatchStore(database_params)

if 'READ_ONLY_REASON' in config:
    print('Tool is in read-only mode according to config')
    sys.exit(1)

deleted_oauths, stopped_backgrounds = batch_store.delete_old_auths()
print(f'Deleted {deleted_oauths} old rows from the `oauth` table (stopped {stopped_backgrounds} background runs.')
