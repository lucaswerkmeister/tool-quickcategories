#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import mwoauth # type: ignore
import os
import signal
import sys
import time
import toolforge
import yaml

from command import CommandFailure
from database import DatabaseStore
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


stopped = False
def on_sigterm(signalnum, frame):
    global stopped
    stopped = True
    print('Received SIGTERM, will stop once the current command is done')
signal.signal(signal.SIGTERM, on_sigterm) # NOQA: E305 (no blank lines after function definition)


while not stopped:
    pending = batch_store.make_plan_pending_background(consumer_token, user_agent)
    if not pending:
        # TODO would be nicer to switch to some better notification mechanism for the app to let the runner know there’s work again
        time.sleep(10)
        continue

    batch, command_pending, session = pending
    if 'summary_suffix' in config:
        summary_suffix = config['summary_suffix'].format(batch.id)
    else:
        summary_suffix = None
    runner = Runner(session, summary_suffix)

    print('Running command %d of batch #%d... ' % (command_pending.id, batch.id), end='', flush=True)
    for attempt in range(5):
        command_finish = runner.run_command(command_pending)
        if isinstance(command_finish, CommandFailure) and command_finish.can_retry_immediately():
            continue
        else:
            break
    print(type(command_finish).__name__, flush=True)
    batch.command_records.store_finish(command_finish)
    if isinstance(command_finish, CommandFailure) and not command_finish.can_continue_batch():
        batch_store.stop_background(batch)

print('Done.')
