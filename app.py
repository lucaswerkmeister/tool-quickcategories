# -*- coding: utf-8 -*-

import cachetools
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
import threading
import toolforge
import traceback
from typing import Any, List, Optional, Tuple
import yaml

from batch import OpenBatch
from command import Command, CommandRecord, CommandPlan, CommandPending, CommandEdit, CommandNoop, CommandFailure, CommandPageMissing, CommandPageProtected, CommandEditConflict, CommandMaxlagExceeded, CommandBlocked, CommandWikiReadOnly
from localuser import LocalUser
import parse_wikitext
import parse_tpsv
from runner import Runner
from store import BatchStore


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
    from database import DatabaseStore
    batch_store = DatabaseStore(app.config['database']) # type: BatchStore
else:
    from in_memory import InMemoryStore
    print('No database configuration, using in-memory store (batches will be lost on every restart)')
    batch_store = InMemoryStore()

stewards_global_user_ids_cache = cachetools.TTLCache(maxsize=1, ttl=24*60*60) # type: cachetools.TTLCache[Any, List[int]]
stewards_global_user_ids_cache_lock = threading.RLock()


def log(type, message):
    if app.config.get('DEBUG_' + type, False):
        print('[%s] %s' % (type, message))


@app.template_global()
def csrf_token() -> str:
    if 'csrf_token' not in flask.session:
        log('CSRF', 'allocating a new token')
        flask.session['csrf_token'] = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(64))
    else:
        log('CSRF', 'reusing token from session')
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

@app.template_global()
def can_start_background() -> bool:
    return flask.g.can_start_background

@app.template_global()
def can_stop_background() -> bool:
    return flask.g.can_stop_background

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
    elif isinstance(command_record, CommandPageProtected):
        command_record_markup = flask.render_template('command_page_protected.html',
                                                      domain=domain,
                                                      command_page_protected=command_record)
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
def render_local_user(local_user: LocalUser) -> flask.Markup:
    return (flask.Markup(r'<a href="https://') +
            flask.Markup.escape(local_user.domain) +
            flask.Markup(r'/wiki/Special:Redirect/user/') +
            flask.Markup.escape(str(local_user.local_user_id)) +
            flask.Markup(r'"><bdi>') +
            flask.Markup.escape(local_user.user_name) +
            flask.Markup(r'</bdi></a>'))

def authenticated_session(domain: str = 'meta.wikimedia.org') -> Optional[mwapi.Session]:
    if 'oauth_access_token' in flask.session:
        access_token = mwoauth.AccessToken(**flask.session['oauth_access_token'])
        auth = requests_oauthlib.OAuth1(client_key=consumer_token.key, client_secret=consumer_token.secret,
                                        resource_owner_key=access_token.key, resource_owner_secret=access_token.secret)
        return mwapi.Session(host='https://'+domain, auth=auth, user_agent=user_agent)
    else:
        return None

def anonymous_session(domain: str = 'meta.wikimedia.org') -> mwapi.Session:
    return mwapi.Session(host='https://'+domain, user_agent=user_agent)

def any_session(domain: str = 'meta.wikimedia.org') -> mwapi.Session:
    return authenticated_session(domain) or anonymous_session(domain)

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

    title = flask.request.form.get('title')
    if title is not None and len(title) > 800:
        return flask.Markup('Title "') + flask.Markup.escape(title) + flask.Markup('" is too long for a summary'), 400

    session = authenticated_session(domain)
    if not session:
        return 'not logged in', 403 # Forbidden; 401 Unauthorized would be inappropriate because we don’t send WWW-Authenticate

    try:
        response = session.get(action='query',
                               meta='siteinfo')
        servername = response['query']['general']['servername']
        if servername != domain:
            message = (flask.Markup(r'The server at <code>') +
                       flask.Markup.escape(domain) +
                       flask.Markup(r'</code> indicates its actual name is <code>') +
                       flask.Markup.escape(servername) +
                       flask.Markup(r'</code>.'))
            return flask.render_template('new_batch_error.html',
                                         message=message), 400
    except Exception:
        traceback.print_exc() # for possible later manual inspection
        message = (flask.Markup(r'Could not connect to the server at <code>') +
                   flask.Markup.escape(domain) +
                   flask.Markup(r'</code>.'))
        return flask.render_template('new_batch_error.html',
                                     message=message), 400

    try:
        batch = parse_tpsv.parse_batch(flask.request.form.get('commands', ''), title=title)
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
        try:
            userinfo = session.get(action='query',
                                   meta='userinfo',
                                   uiprop=['groups', 'centralids'])['query']['userinfo']
        except mwapi.errors.APIError as e:
            if e.code == 'mwoauth-invalid-authorization-invalid-user':
                # user is viewing a batch for a wiki where they do not have a local user account
                # treat as anonymous on the local wiki, but query Meta to find out if they’re a steward
                local_user_id = None # type: Optional[int]
                groups = [] # type: List[str]
                meta_session = authenticated_session('meta.wikimedia.org') # type: mwapi.Session
                meta_userinfo = meta_session.get(action='query',
                                                 meta='userinfo',
                                                 uiprop=['centralids'])['query']['userinfo']
                global_user_id = meta_userinfo['centralids']['CentralAuth']
            else:
                raise e
        else:
            local_user_id = userinfo['id']
            groups = userinfo['groups']
            global_user_id = userinfo['centralids']['CentralAuth']
        flask.g.can_run_commands = local_user_id == batch.local_user.local_user_id
        flask.g.can_start_background = flask.g.can_run_commands and \
            'autoconfirmed' in groups and \
            isinstance(batch, OpenBatch)
        flask.g.can_stop_background = flask.g.can_start_background or \
            'sysop' in groups or \
            global_user_id in steward_global_user_ids()
    else:
        flask.g.can_run_commands = False
        flask.g.can_start_background = False
        flask.g.can_stop_background = False

    if batch.title:
        title = parse_wikitext.parse_summary(anonymous_session(batch.domain), batch.title) # type: Optional[flask.Markup]
    else:
        title = None

    offset, limit = slice_from_args(flask.request.args)

    return flask.render_template('batch.html',
                                 batch=batch,
                                 title=title,
                                 offset=offset,
                                 limit=limit)

@app.route('/batch/<int:id>/background_history')
def batch_background_history(id: int):
    batch = batch_store.get_batch(id)
    if batch is None:
        return flask.render_template('batch_not_found.html',
                                     id=id), 404

    return flask.render_template('background_history.html',
                                 batch=batch)

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
    if local_user_id != batch.local_user.local_user_id:
        return 'may not run this batch', 403

    if 'summary_batch_link' in app.config:
        summary_batch_link = app.config['summary_batch_link'].format(id)
    else:
        summary_batch_link = None

    runner = Runner(session, batch.title, summary_batch_link)

    offset, limit = slice_from_args(flask.request.form)
    command_pendings = batch.command_records.make_plans_pending(offset, limit)

    try:
        runner.prepare_pages([command_pending.command.page for command_pending in command_pendings])
        for command_pending in command_pendings:
            for attempt in range(5):
                command_finish = runner.run_command(command_pending)
                if isinstance(command_finish, CommandFailure) and command_finish.can_retry_immediately():
                    continue
                else:
                    break
            batch.command_records.store_finish(command_finish)
            if isinstance(command_finish, CommandFailure):
                can_continue = command_finish.can_continue_batch()
                if isinstance(can_continue, datetime.datetime):
                    batch_store.suspend_background(batch, until=can_continue)
                    break
                elif not can_continue:
                    batch_store.stop_background(batch)
                    break
    finally:
        batch.command_records.make_pendings_planned([command_pending.id for command_pending in command_pendings])

    return flask.redirect(flask.url_for('batch',
                                        id=id,
                                        offset=offset,
                                        limit=limit))

@app.route('/batch/<int:id>/start_background', methods=['POST'])
def start_batch_background(id: int):
    batch = batch_store.get_batch(id)
    if batch is None:
        return flask.render_template('batch_not_found.html',
                                     id=id), 404
    if not isinstance(batch, OpenBatch):
        return 'not an open batch', 400

    session = authenticated_session(batch.domain)
    if not session:
        return 'not logged in', 403
    userinfo = session.get(action='query',
                           meta='userinfo',
                           uiprop=['groups'])['query']['userinfo']
    local_user_id = userinfo['id']
    if local_user_id != batch.local_user.local_user_id or \
       'autoconfirmed' not in userinfo['groups']:
        return 'may not start this batch in background', 403

    batch_store.start_background(batch, session)

    offset, limit = slice_from_args(flask.request.form)
    return flask.redirect(flask.url_for('batch',
                                        id=id,
                                        offset=offset,
                                        limit=limit))

@app.route('/batch/<int:id>/stop_background', methods=['POST'])
def stop_batch_background(id: int):
    batch = batch_store.get_batch(id)
    if batch is None:
        return flask.render_template('batch_not_found.html',
                                     id=id), 404

    session = authenticated_session(batch.domain)
    if not session:
        return 'not logged in', 403
    userinfo = session.get(action='query',
                           meta='userinfo',
                           uiprop=['groups', 'centralids'])['query']['userinfo']
    local_user_id = userinfo['id']
    global_user_id = userinfo['centralids']['CentralAuth']
    if local_user_id != batch.local_user.local_user_id and \
       'sysop' not in userinfo['groups'] and \
       global_user_id not in steward_global_user_ids():
        return 'may not stop this batch in background', 403

    batch_store.stop_background(batch, session)

    offset, limit = slice_from_args(flask.request.form)
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

@cachetools.cached(cache=stewards_global_user_ids_cache,
                   key=lambda: '#stewards',
                   lock=stewards_global_user_ids_cache_lock)
def steward_global_user_ids() -> List[int]:
    session = mwapi.Session(host='https://meta.wikimedia.org', user_agent=user_agent)
    ids = []
    for result in session.get(action='query',
                              list='allusers',
                              augroup=['steward'],
                              auprop=['centralids'],
                              aulimit='max',
                              continuation=True):
        for user in result['query']['allusers']:
            ids.append(user['centralids']['CentralAuth'])
    return ids


def full_url(endpoint: str, **kwargs) -> str:
    scheme = flask.request.headers.get('X-Forwarded-Proto', 'http')
    return flask.url_for(endpoint, _external=True, _scheme=scheme, **kwargs)

@app.template_global()
def current_url(external: bool = False) -> str:
    all_args = {}
    for args in [flask.request.args, flask.request.view_args]:
        all_args.update(args)
    # in Python 3.5+, replace that with **flask.request.args, **flask.request.view_args

    if external:
        return flask.url_for(flask.request.endpoint,
                             _external=True,
                             _scheme=flask.request.headers.get('X-Forwarded-Proto', 'http'),
                             **all_args)
    else:
        return flask.url_for(flask.request.endpoint,
                             **all_args)

def submitted_request_valid() -> bool:
    """Check whether a submitted POST request is valid.

    If this method returns False, the request might have been issued
    by an attacker as part of a Cross-Site Request Forgery attack;
    callers MUST NOT process the request in that case.
    """
    real_token = flask.session.pop('csrf_token', None)
    log('CSRF', 'invalidated token from session')
    submitted_token = flask.request.form.get('csrf_token', None)
    if not real_token:
        # we never expected a POST
        log('CSRF', 'no real token')
        return False
    if not submitted_token:
        # token got lost or attacker did not supply it
        log('CSRF', 'no submitted token')
        return False
    if submitted_token != real_token:
        # incorrect token (could be outdated or incorrectly forged)
        log('CSRF', 'token mismatch')
        return False
    if not (flask.request.referrer or '').startswith(full_url('index')):
        # correct token but not coming from the correct page; for
        # example, JS running on https://tools.wmflabs.org/tool-a is
        # allowed to access https://tools.wmflabs.org/tool-b and
        # extract CSRF tokens from it (since both of these pages are
        # hosted on the https://tools.wmflabs.org domain), so checking
        # the Referer header is our only protection against attackers
        # from other Toolforge tools
        log('CSRF', 'referrer mismatch: should start with %s, got %s' % (full_url('index'), flask.request.referrer))
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
