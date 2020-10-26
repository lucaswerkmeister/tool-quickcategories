#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import mwoauth  # type: ignore
import os
import random
import signal
import sys
import time
import toolforge
from typing import Any
import yaml

from command import CommandFailure
from database import DatabaseStore
from querytime import flush_querytime
from runner import Runner


user_agent = toolforge.set_user_agent('quickcategories', email='mail@lucaswerkmeister.de')

__dir__ = os.path.dirname(__file__)
try:
    with open(os.path.join(__dir__, 'config.yaml')) as config_file:
        config = yaml.safe_load(config_file)
except FileNotFoundError:
    print('config.yaml file not found, cannot run in background')
    sys.exit(1)

if 'oauth' in config:
    consumer_token = mwoauth.ConsumerToken(config['oauth']['consumer_key'], config['oauth']['consumer_secret'])
else:
    print('No OAuth configuration in config.yaml file, cannot run in background')
    sys.exit(1)

if 'database' in config:
    batch_store = DatabaseStore(config['database'])
else:
    print('No database configuration, cannot run in background')
    sys.exit(1)

if 'read_only_reason' in config:
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

        if 'summary_batch_link' in config:
            summary_batch_link = config['summary_batch_link'].format(batch.id)
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
