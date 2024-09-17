#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import flask
import os
import random
import signal
import sys
import time
from typing import Any

from command import CommandFailure
from database import DatabaseStore
from init import user_agent, load_config, load_consumer_token, load_database_params
from querytime import flush_querytime
from runner import Runner


config = flask.Config(os.path.dirname(__file__))
has_config = load_config(config)

if not has_config:
    print('No configuration found, cannot run in background')
    sys.exit(1)

consumer_token = load_consumer_token(config)
if consumer_token is None:
    print('No OAuth configuration found, cannot run in background')
    sys.exit(1)

database_params = load_database_params(config)
if database_params is None:
    print('No database configuration, cannot run in background')
    sys.exit(1)
batch_store = DatabaseStore(database_params)

if 'READ_ONLY_REASON' in config:
    print('Tool is in read-only mode according to config')
    sys.exit(1)


stopped = False
def on_sigterm(signalnum: int, frame: Any) -> None:
    global stopped
    stopped = True
    print('Received SIGTERM, will stop once the current command is done', flush=True)
signal.signal(signal.SIGTERM, on_sigterm)  # NOQA: E305 (no blank lines after function definition)


while not stopped:
    pending = batch_store.make_plan_pending_background(consumer_token, user_agent)
    if not pending:
        if random.randrange(16) == 0:
            with batch_store.connect() as connection:
                flush_querytime(connection)
        # TODO would be nicer to switch to some better notification mechanism for the app to let the runner know there’s work again
        # (but note that suspended background commands can start yielding pending commands at basically any time again)
        time.sleep(10)
        continue
    else:
        if random.randrange(128) == 0:
            with batch_store.connect() as connection:
                flush_querytime(connection)
    batch, command_pending, session = pending

    try:
        print('Running command %d of batch #%d... ' % (command_pending.id, batch.id), end='', flush=True)

        if 'SUMMARY_BATCH_LINK' in config:
            summary_batch_link = config['SUMMARY_BATCH_LINK'].format(batch.id)
        else:
            summary_batch_link = None
        runner = Runner(session, batch.title, summary_batch_link)

        for attempt in range(5):
            command_finish = runner.run_command(command_pending)
            if isinstance(command_finish, CommandFailure) and command_finish.can_retry_immediately():
                continue
            else:
                break
        print(type(command_finish).__name__, flush=True)
        batch.command_records.store_finish(command_finish)
        if isinstance(command_finish, CommandFailure):
            can_continue = command_finish.can_continue_batch()
            if isinstance(can_continue, datetime.datetime):
                batch_store.suspend_background(batch, until=can_continue)
            elif not can_continue:
                batch_store.stop_background(batch)
    finally:
        batch.command_records.make_pendings_planned([command_pending.id])

print('Done.')
