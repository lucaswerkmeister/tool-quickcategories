# -*- coding: utf-8 -*-

import datetime
import flask
import humanize
import mwapi # type: ignore
import mwoauth # type: ignore
import os
import random
import re
import requests_oauthlib # type: ignore
import string
import toolforge
from typing import List, Optional, Tuple
import yaml

from batch import StoredBatch
from command import Command, CommandRecord, CommandPlan, CommandPending, CommandEdit, CommandNoop, CommandFailure, CommandPageMissing, CommandEditConflict, CommandMaxlagExceeded, CommandBlocked, CommandWikiReadOnly
import parse_tpsv
from runner import Runner
import store


app = flask.Flask(__name__)

user_agent = toolforge.set_user_agent('quickcategories', email='mail@lucaswerkmeister.de')

__dir__ = os.path.dirname(__file__)
try:
    with open(os.path.join(__dir__, 'config.yaml')) as config_file:
        app.config.update(yaml.safe_load(config_file))
except FileNotFoundError:
    print('config.yaml file not found, assuming local development setup')
    app.secret_key = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(64))

if 'oauth' in app.config:
    consumer_token = mwoauth.ConsumerToken(app.config['oauth']['consumer_key'], app.config['oauth']['consumer_secret'])

if 'database' in app.config:
    batch_store = store.DatabaseStore(app.config['database']) # type: store.BatchStore
else:
    print('No database configuration, using in-memory store (batches will be lost on every restart)')
    batch_store = store.InMemoryStore()


@app.template_global()
def csrf_token() -> str:
    if 'csrf_token' not in flask.session:
        flask.session['csrf_token'] = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(64))
    return flask.session['csrf_token']

@app.template_global()
def form_value(name: str) -> flask.Markup:
    if 'repeat_form' in flask.g and name in flask.request.form:
        return (flask.Markup(r' value="') +
                flask.Markup.escape(flask.request.form[name]) +
                flask.Markup(r'" '))
    else:
        return flask.Markup()

@app.template_global()
def form_attributes(name: str) -> flask.Markup:
    return (flask.Markup(r' id="') +
            flask.Markup.escape(name) +
            flask.Markup(r'" name="') +
            flask.Markup.escape(name) +
            flask.Markup(r'" ') +
            form_value(name))

@app.template_filter()
def user_link(user_name: str) -> flask.Markup:
    return (flask.Markup(r'<a href="https://meta.wikimedia.org/wiki/User:') +
            flask.Markup.escape(user_name.replace(' ', '_')) +
            flask.Markup(r'">') +
            flask.Markup(r'<bdi>') +
            flask.Markup.escape(user_name) +
            flask.Markup(r'</bdi>') +
            flask.Markup(r'</a>'))

@app.template_global()
def user_logged_in() -> bool:
    return authenticated_session() is not None

@app.template_global()
def authentication_area() -> flask.Markup:
    if 'oauth' not in app.config:
        return flask.Markup()

    if 'oauth_access_token' not in flask.session:
        return (flask.Markup(r'<a id="login" class="navbar-text" href="') +
                flask.Markup.escape(flask.url_for('login')) +
                flask.Markup(r'">Log in</a>'))

    access_token = mwoauth.AccessToken(**flask.session['oauth_access_token'])
    identity = mwoauth.identify('https://meta.wikimedia.org/w/index.php',
                                consumer_token,
                                access_token)

    return (flask.Markup(r'<span class="navbar-text">Logged in as ') +
            user_link(identity['username']) +
            flask.Markup(r'</span>'))

@app.template_global()
def can_run_commands(command_records: List[CommandRecord]) -> bool:
    return flask.g.can_run_commands and any(filter(lambda command_record: isinstance(command_record, CommandPlan), command_records))

@app.template_global() # TODO make domain part of Command and turn this into a template filter?
def render_command(command: Command, domain: str) -> flask.Markup:
    return flask.Markup(flask.render_template('command.html',
                                              domain=domain,
                                              command=command))

@app.template_global() # TODO also turn into a template filter?
def render_command_record(command_record: CommandRecord, domain: str) -> flask.Markup:
    if isinstance(command_record, CommandPlan):
        command_record_markup = flask.render_template('command_plan.html',
                                                      domain=domain,
                                                      command_plan=command_record)
    elif isinstance(command_record, CommandPending):
        command_record_markup = flask.render_template('command_pending.html',
                                                      domain=domain,
                                                      command_pending=command_record)
    elif isinstance(command_record, CommandEdit):
        command_record_markup = flask.render_template('command_edit.html',
                                                      domain=domain,
                                                      command_edit=command_record)
    elif isinstance(command_record, CommandNoop):
        command_record_markup = flask.render_template('command_noop.html',
                                                      domain=domain,
                                                      command_noop=command_record)
    elif isinstance(command_record, CommandPageMissing):
        command_record_markup = flask.render_template('command_page_missing.html',
                                                      domain=domain,
                                                      command_page_missing=command_record)
    elif isinstance(command_record, CommandEditConflict):
        command_record_markup = flask.render_template('command_edit_conflict.html',
                                                      domain=domain,
                                                      command_edit_conflict=command_record)
    elif isinstance(command_record, CommandMaxlagExceeded):
        command_record_markup = flask.render_template('command_maxlag_exceeded.html',
                                                      domain=domain,
                                                      command_maxlag_exceeded=command_record)
    elif isinstance(command_record, CommandBlocked):
        command_record_markup = flask.render_template('command_blocked.html',
                                                      domain=domain,
                                                      command_blocked=command_record)
    elif isinstance(command_record, CommandWikiReadOnly):
        command_record_markup = flask.render_template('command_wiki_read_only.html',
                                                      domain=domain,
                                                      command_blocked=command_record)
    else:
        raise ValueError('Unknown command record type')

    return flask.Markup(command_record_markup)

@app.template_filter()
def render_datetime(dt: datetime.datetime) -> flask.Markup:
    naive_dt = dt.astimezone().replace(tzinfo=None) # humanize doesn’t support timezones :(
    return (flask.Markup(r'<time datetime="') +
            flask.Markup.escape(dt.isoformat()) +
            flask.Markup(r'" title="') +
            flask.Markup.escape(dt.isoformat()) +
            flask.Markup(r'">') +
            flask.Markup.escape(humanize.naturaltime(naive_dt)) +
            flask.Markup(r'</time>'))

@app.template_global()
def render_batch_user(batch: StoredBatch) -> flask.Markup:
    return (flask.Markup(r'<a href="https://') +
            flask.Markup.escape(batch.domain) +
            flask.Markup(r'/wiki/Special:Redirect/user/') +
            flask.Markup.escape(str(batch.local_user_id)) +
            flask.Markup(r'"><bdi>') +
            flask.Markup.escape(batch.user_name) +
            flask.Markup(r'</bdi></a>'))

def authenticated_session(domain: str = 'meta.wikimedia.org') -> Optional[mwapi.Session]:
    if 'oauth_access_token' in flask.session:
        access_token = mwoauth.AccessToken(**flask.session['oauth_access_token'])
        auth = requests_oauthlib.OAuth1(client_key=consumer_token.key, client_secret=consumer_token.secret,
                                        resource_owner_key=access_token.key, resource_owner_secret=access_token.secret)
        return mwapi.Session(host='https://'+domain, auth=auth, user_agent=user_agent)
    else:
        return None

@app.route('/')
def index():
    return flask.render_template('index.html', latest_batches=batch_store.get_latest_batches())

@app.route('/batch', methods=['POST'])
def new_batch():
    if not submitted_request_valid():
        return 'CSRF error', 400

    domain = flask.request.form.get('domain', '(not provided)')
    if not is_wikimedia_domain(domain):
        return flask.Markup.escape(domain) + flask.Markup(' is not recognized as a Wikimedia domain'), 400

    session = authenticated_session(domain)
    if not session:
        return 'not logged in', 403 # Forbidden; 401 Unauthorized would be inappropriate because we don’t send WWW-Authenticate

    try:
        batch = parse_tpsv.parse_batch(flask.request.form.get('commands', ''))
    except parse_tpsv.ParseBatchError as e:
        return str(e)

    batch.cleanup()

    id = batch_store.store_batch(batch, session).id
    return flask.redirect(flask.url_for('batch', id=id))

@app.route('/batch/<int:id>/')
def batch(id: int):
    batch = batch_store.get_batch(id)
    if batch is None:
        return flask.render_template('batch_not_found.html',
                                     id=id), 404

    session = authenticated_session(batch.domain)
    if session:
        local_user_id = session.get(action='query',
                                    meta='userinfo')['query']['userinfo']['id']
        flask.g.can_run_commands = local_user_id == batch.local_user_id
    else:
        flask.g.can_run_commands = False

    offset, limit = slice_from_args(flask.request.args)

    return flask.render_template('batch.html',
                                 batch=batch,
                                 offset=offset,
                                 limit=limit)

@app.route('/batch/<int:id>/run_slice', methods=['POST'])
def run_batch_slice(id: int):
    batch = batch_store.get_batch(id)
    if batch is None:
        return flask.render_template('batch_not_found.html',
                                     id=id), 404

    session = authenticated_session(batch.domain)
    if not session:
        return 'not logged in', 403
    local_user_id = session.get(action='query',
                                meta='userinfo')['query']['userinfo']['id']
    if local_user_id != batch.local_user_id:
        return 'may not run this batch', 403

    if 'summary_suffix' in app.config:
        summary_suffix = app.config['summary_suffix'].format(id)
    else:
        summary_suffix = None

    runner = Runner(session, summary_suffix)

    offset, limit = slice_from_args(flask.request.form)
    command_pendings = batch.command_records.make_plans_pending(offset, limit)

    runner.prepare_pages([command_pending.command.page for command_pending in command_pendings])
    for command_pending in command_pendings:
        for attempt in range(5):
            command_finish = runner.run_command(command_pending)
            if isinstance(command_finish, CommandFailure) and command_finish.can_retry_immediately():
                continue
            else:
                break
        batch.command_records.store_finish(command_finish)
        if isinstance(command_finish, CommandFailure) and not command_finish.can_continue_batch():
            break

    return flask.redirect(flask.url_for('batch',
                                        id=id,
                                        offset=offset,
                                        limit=limit))

@app.route('/login')
def login():
    redirect, request_token = mwoauth.initiate('https://meta.wikimedia.org/w/index.php', consumer_token, user_agent=user_agent)
    flask.session['oauth_request_token'] = dict(zip(request_token._fields, request_token))
    return flask.redirect(redirect)

@app.route('/oauth/callback')
def oauth_callback():
    request_token = mwoauth.RequestToken(**flask.session.pop('oauth_request_token'))
    access_token = mwoauth.complete('https://meta.wikimedia.org/w/index.php', consumer_token, request_token, flask.request.query_string, user_agent=user_agent)
    flask.session['oauth_access_token'] = dict(zip(access_token._fields, access_token))
    return flask.redirect(flask.url_for('index'))


def is_wikimedia_domain(domain: str) -> bool:
    return re.fullmatch(r'[a-z0-9-]+\.(?:wiki(?:pedia|media|books|data|news|quote|source|versity|voyage)|mediawiki|wiktionary)\.org', domain) is not None

def slice_from_args(args: dict) -> Tuple[int, int]:
    try:
        offset = int(args['offset'])
    except (KeyError, ValueError):
        offset = 0
    offset = max(0, offset)

    try:
        limit = int(args['limit'])
    except (KeyError, ValueError):
        limit = 50
    limit = max(1, min(500, limit))

    return offset, limit


def full_url(endpoint: str, **kwargs) -> str:
    scheme = flask.request.headers.get('X-Forwarded-Proto', 'http')
    return flask.url_for(endpoint, _external=True, _scheme=scheme, **kwargs)

def submitted_request_valid() -> bool:
    """Check whether a submitted POST request is valid.

    If this method returns False, the request might have been issued
    by an attacker as part of a Cross-Site Request Forgery attack;
    callers MUST NOT process the request in that case.
    """
    real_token = flask.session.pop('csrf_token', None)
    submitted_token = flask.request.form.get('csrf_token', None)
    if not real_token:
        # we never expected a POST
        return False
    if not submitted_token:
        # token got lost or attacker did not supply it
        return False
    if submitted_token != real_token:
        # incorrect token (could be outdated or incorrectly forged)
        return False
    if not (flask.request.referrer or '').startswith(full_url('index')):
        # correct token but not coming from the correct page; for
        # example, JS running on https://tools.wmflabs.org/tool-a is
        # allowed to access https://tools.wmflabs.org/tool-b and
        # extract CSRF tokens from it (since both of these pages are
        # hosted on the https://tools.wmflabs.org domain), so checking
        # the Referer header is our only protection against attackers
        # from other Toolforge tools
        return False
    return True

@app.after_request
def deny_frame(response: flask.Response) -> flask.Response:
    """Disallow embedding the tool’s pages in other websites.

    If other websites can embed this tool’s pages, e. g. in <iframe>s,
    other tools hosted on tools.wmflabs.org can send arbitrary web
    requests from this tool’s context, bypassing the referrer-based
    CSRF protection.
    """
    response.headers['X-Frame-Options'] = 'deny'
    return response
