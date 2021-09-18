from dataclasses import dataclass
import datetime
import mwapi  # type: ignore
from typing import Dict, List, Optional, cast

from command import CommandPending, CommandFinish, CommandEdit, CommandNoop, CommandPageMissing, CommandTitleInvalid, CommandPageProtected, CommandEditConflict, CommandMaxlagExceeded, CommandBlocked, CommandWikiReadOnly
from page import Page
import siteinfo


@dataclass
class Runner():

    session: mwapi.Session
    summary_batch_title: Optional[str] = None
    summary_batch_link: Optional[str] = None

    def __post_init__(self) -> None:
        self.csrf_token = self.session.get(action='query',
                                           meta='tokens')['query']['tokens']['csrftoken']

    def resolve_pages(self, pages: List[Page]) -> None:
        pages_with_resolve_redirects: List[Page] = []
        pages_without_resolve_redirects: List[Page] = []

        for page in pages:
            if self.do_resolve_redirects(page.resolve_redirects):
                pages_with_resolve_redirects.append(page)
            else:
                pages_without_resolve_redirects.append(page)

        if pages_with_resolve_redirects:
            self.resolve_pages_of_one_kind(pages_with_resolve_redirects)
        if pages_without_resolve_redirects:
            self.resolve_pages_of_one_kind(pages_without_resolve_redirects)

    def do_resolve_redirects(self, resolve_redirects: Optional[bool]) -> bool:
        return resolve_redirects is True  # None is equivalent to False

    def resolve_pages_of_one_kind(self, pages: List[Page]) -> None:
        assert pages
        assert len(pages) <= 50

        do_resolve_redirects = self.do_resolve_redirects(pages[0].resolve_redirects)

        pages_by_title: Dict[str, Page] = {}
        titles: List[str] = []
        for page in pages:
            if self.do_resolve_redirects(page.resolve_redirects) != do_resolve_redirects:
                raise ValueError('pages were not all of one kind')
            pages_by_title[page.title] = page
            titles.append(page.title)

        # TODO pass redirects=do_resolve_redirects to session.get()
        # once there is an mwapi release with support for boolean parameters
        params = {
            'action': 'query',
            'titles': titles,
            'prop': ['revisions'],
            'rvprop': ['ids', 'content', 'contentmodel', 'timestamp'],
            'rvslots': ['main'],
            'curtimestamp': True,
            'formatversion': 2,
        }
        if do_resolve_redirects:
            params['redirects'] = True
        response = self.session.get(**params)

        for normalization in response['query'].get('normalized', []):
            pages_by_title[normalization['to']] = pages_by_title[normalization['from']]

        if do_resolve_redirects:
            for redirect in response['query'].get('redirects', []):
                pages_by_title[redirect['to']] = pages_by_title[redirect['from']]

        for response_page in response['query']['pages']:
            title = response_page['title']
            page = pages_by_title[title]
            if 'missing' in response_page:
                page.resolution = {
                    'missing': True,
                    'curtimestamp': response['curtimestamp'],
                }
                continue
            if 'invalid' in response_page:
                page.resolution = {
                    'invalid': True,
                    'curtimestamp': response['curtimestamp'],
                }
                continue
            revision = response_page['revisions'][0]
            slot = revision['slots']['main']
            if slot['contentmodel'] != 'wikitext' or slot['contentformat'] != 'text/x-wiki':
                raise ValueError('Unexpected content model or format for revision %d of page %s, refusing to edit!' % (revision['revid'], title))
            page.resolution = {
                'wikitext': slot['content'],
                'page_id': response_page['pageid'],
                'base_timestamp': revision['timestamp'],
                'base_revid': revision['revid'],
                'start_timestamp': response['curtimestamp'],
            }

    def run_command(self, command_pending: CommandPending) -> CommandFinish:
        page = command_pending.command.page
        if page.resolution is None:
            self.resolve_pages([page])
        resolution = cast(dict, page.resolution)
        category_info = siteinfo.category_info(self.session)

        if 'missing' in resolution:
            return CommandPageMissing(command_pending.id, command_pending.command, curtimestamp=resolution['curtimestamp'])
        if 'invalid' in resolution:
            return CommandTitleInvalid(command_pending.id, command_pending.command, curtimestamp=resolution['curtimestamp'])

        wikitext, actions = command_pending.command.apply(resolution['wikitext'], category_info)
        summary = ''
        major_commands, minor_commands = 0, 0
        for action, noop in actions:
            action_summary = action.summary(category_info)
            if noop:
                action_summary = siteinfo.parentheses(self.session, action_summary)
            else:
                if action.is_minor():
                    minor_commands += 1
                else:
                    major_commands += 1
            if summary:
                summary += siteinfo.comma_separator(self.session)
            summary += action_summary

        if self.summary_batch_title:
            summary += siteinfo.semicolon_separator(self.session)
            summary += self.summary_batch_title
            if self.summary_batch_link:
                summary += siteinfo.word_separator(self.session)
                summary += siteinfo.parentheses(self.session, self.summary_batch_link)
        elif self.summary_batch_link:
            summary += siteinfo.semicolon_separator(self.session)
            summary += self.summary_batch_link

        if wikitext == resolution['wikitext']:
            return CommandNoop(command_pending.id, command_pending.command, resolution['base_revid'])
        try:
            params = {'action': 'edit',
                      'pageid': resolution['page_id'],
                      'text': wikitext,
                      'summary': summary,
                      'bot': True,
                      'basetimestamp': resolution['base_timestamp'],
                      'starttimestamp': resolution['start_timestamp'],
                      'contentformat': 'text/x-wiki',
                      'contentmodel': 'wikitext',
                      'token': self.csrf_token,
                      'assert': 'user',
                      'maxlag': 5,
                      'formatversion': 2}
            if minor_commands < 2 and not major_commands:
                params['minor'] = ''
            response = self.session.post(**params)
        except mwapi.errors.APIError as e:
            if e.code == 'editconflict':
                page.resolution = None  # this must be outdated now
                return CommandEditConflict(command_pending.id, command_pending.command)
            elif e.code == 'protectedpage':
                return CommandPageProtected(command_pending.id, command_pending.command, curtimestamp=resolution['start_timestamp'])
            elif e.code == 'maxlag':
                retry_after_seconds = 5  # the API returns this in a Retry-After header, but mwapi hides that from us :(
                retry_after = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=retry_after_seconds)
                retry_after = retry_after.replace(microsecond=0)
                return CommandMaxlagExceeded(command_pending.id, command_pending.command, retry_after)
            elif e.code == 'blocked' or e.code == 'autoblocked':
                auto = e.code == 'autoblocked'
                blockinfo = None  # the API returns this in a 'blockinfo' member of the 'error' object, but mwapi hides that from us :(
                return CommandBlocked(command_pending.id, command_pending.command, auto, blockinfo)
            elif e.code == 'readonly':
                reason = None  # the API returns this in a 'readonlyreason' member of the 'error' object, but mwapi hides that from us :(
                # maintenance-related read-only times are usually done within a few minutes (though scheduled for an hour),
                # and MediaWiki automatically enters temporary read-only mode if replication lag exceeds 30 seconds,
                # so guess a fairly short retry time
                retry_after_minutes = 5
                retry_after = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=retry_after_minutes)
                retry_after = retry_after.replace(microsecond=0)
                return CommandWikiReadOnly(command_pending.id, command_pending.command, reason, retry_after)
            else:
                raise e

        if 'nochange' in response['edit']:
            page.resolution = None  # this must be outdated now, otherwise we would’ve detected the no-op before trying to edit
            return CommandNoop(command_pending.id, command_pending.command, resolution['base_revid'])

        assert response['edit']['oldrevid'] == resolution['base_revid']
        page.resolution = None  # this must be outdated now, and we don’t know the new wikitext since non-conflicting edits may have been merged
        return CommandEdit(command_pending.id, command_pending.command, response['edit']['oldrevid'], response['edit']['newrevid'])
