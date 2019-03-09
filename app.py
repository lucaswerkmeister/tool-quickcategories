# -*- coding: utf-8 -*-

import flask # type: ignore
import mwapi # type: ignore
import mwoauth # type: ignore
import os
import random
import re
import requests_oauthlib # type: ignore
import string
import toolforge
from typing import cast, Dict, List, Optional
import yaml

from command import Command, CommandRecord, CommandPlan, CommandEdit, CommandNoop
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
def render_command(command: Command, domain: str):
    return flask.Markup(flask.render_template('command.html',
                                              domain=domain,
                                              command=command))

@app.template_global() # TODO also turn into a template filter?
def render_command_record(command_record: CommandRecord, domain: str):
    if isinstance(command_record, CommandPlan):
        command_record_markup = flask.render_template('command_plan.html',
                                                      domain=domain,
                                                      command_plan=command_record)
    elif isinstance(command_record, CommandEdit):
        command_record_markup = flask.render_template('command_edit.html',
                                                      domain=domain,
                                                      command_edit=command_record)
    elif isinstance(command_record, CommandNoop):
        command_record_markup = flask.render_template('command_noop.html',
                                                      domain=domain,
                                                      command_noop=command_record)
    else:
        raise ValueError('Unknown command record type')

    return flask.Markup(command_record_markup)

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
    return flask.render_template('index.html')

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

    return flask.render_template('batch.html',
                                 batch=batch,
                                 slice=slice_from_args(flask.request.args))

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

    runner = Runner(session)

    slice = slice_from_args(flask.request.form)
    offset = cast(int, slice.start) # start is Optional[int], but slice_from_args always returns full slices
    limit = cast(int, slice.stop) - offset # similar

    command_plans = {} # type: Dict[int, CommandPlan]
    for index, command_plan in enumerate(batch.command_records[slice]):
        if not isinstance(command_plan, CommandPlan):
            continue
        command_plans[offset+index] = command_plan

    runner.prepare_pages([command_plan.command.page for command_plan in command_plans.values()])
    for index, command_plan in command_plans.items():
        batch.command_records[index] = runner.run_command(command_plan)

    return flask.redirect(flask.url_for('batch',
                                        id=id,
                                        offset=offset,
                                        limit=limit))

@app.route('/greet/<name>')
def greet(name: str):
    return flask.render_template('greet.html',
                                 name=name)

@app.route('/praise', methods=['GET', 'POST'])
def praise():
    csrf_error = False
    if flask.request.method == 'POST':
        if submitted_request_valid():
            flask.session['praise'] = flask.request.form.get('praise', 'praise missing')
        else:
            csrf_error = True
            flask.g.repeat_form = True

    session = authenticated_session()
    if session:
        userinfo = session.get(action='query', meta='userinfo', uiprop='options')['query']['userinfo']
        name = userinfo['name']
        gender = userinfo['options']['gender']
        if gender == 'male':
            default_praise = 'Praise him with great praise!'
        elif gender == 'female':
            default_praise = 'Praise her with great praise!'
        else:
            default_praise = 'Praise them with great praise!'
    else:
        name = None
        default_praise = 'You rock!'

    praise = flask.session.get('praise', default_praise)

    return flask.render_template('praise.html',
                                 name=name,
                                 praise=praise,
                                 csrf_error=csrf_error)

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

def slice_from_args(args: dict) -> slice:
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

    return slice(offset, offset+limit)


def full_url(endpoint: str, **kwargs) -> str:
    scheme=flask.request.headers.get('X-Forwarded-Proto', 'http')
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
