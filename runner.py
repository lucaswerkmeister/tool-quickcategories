import datetime
import mwapi # type: ignore
from typing import Dict, List, Optional

from command import CommandPending, CommandFinish, CommandEdit, CommandNoop, CommandPageMissing, CommandTitleInvalid, CommandPageProtected, CommandEditConflict, CommandMaxlagExceeded, CommandBlocked, CommandWikiReadOnly
import siteinfo


class Runner():

    def __init__(self, session: mwapi.Session, summary_batch_title: Optional[str] = None, summary_batch_link: Optional[str] = None):
        self.session = session
        self.csrf_token = session.get(action='query',
                                      meta='tokens')['query']['tokens']['csrftoken']
        self.summary_batch_title = summary_batch_title
        self.summary_batch_link = summary_batch_link
        self.prepared_pages = {} # type: Dict[str, dict]

    def prepare_pages(self, titles: List[str]):
        assert titles
        assert len(titles) <= 50

        response = self.session.get(action='query',
                                    titles=titles,
                                    prop=['revisions'],
                                    rvprop=['ids', 'content', 'contentmodel', 'timestamp'],
                                    rvslots=['main'],
                                    curtimestamp=True,
                                    formatversion=2)

        for page in response['query']['pages']:
            title = page['title']
            if 'missing' in page:
                self.prepared_pages[title] = {
                    'missing': True,
                    'curtimestamp': response['curtimestamp'],
                }
                continue
            if 'invalid' in page:
                self.prepared_pages[title] = {
                    'invalid': True,
                    'curtimestamp': response['curtimestamp'],
                }
                continue
            revision = page['revisions'][0]
            slot = revision['slots']['main']
            if slot['contentmodel'] != 'wikitext' or slot['contentformat'] != 'text/x-wiki':
                raise ValueError('Unexpected content model or format for revision %d of page %s, refusing to edit!' % (revision['revid'], title))
            self.prepared_pages[title] = {
                'wikitext': slot['content'],
                'page_id': page['pageid'],
                'base_timestamp': revision['timestamp'],
                'base_revid': revision['revid'],
                'start_timestamp': response['curtimestamp'],
            }

        for normalization in response['query'].get('normalized', {}):
            self.prepared_pages[normalization['from']] = self.prepared_pages[normalization['to']]

    def run_command(self, command_pending: CommandPending) -> CommandFinish:
        title = command_pending.command.page
        if title not in self.prepared_pages:
            self.prepare_pages([title])
        prepared_page = self.prepared_pages[title]
        category_info = siteinfo.category_info(self.session)

        if 'missing' in prepared_page:
            return CommandPageMissing(command_pending.id, command_pending.command, curtimestamp=prepared_page['curtimestamp'])
        if 'invalid' in prepared_page:
            return CommandTitleInvalid(command_pending.id, command_pending.command, curtimestamp=prepared_page['curtimestamp'])

        wikitext, actions = command_pending.command.apply(prepared_page['wikitext'], category_info)
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

        if wikitext == prepared_page['wikitext']:
            return CommandNoop(command_pending.id, command_pending.command, prepared_page['base_revid'])
        try:
            params = {'action': 'edit',
                      'pageid': prepared_page['page_id'],
                      'text': wikitext,
                      'summary': summary,
                      'bot': True,
                      'basetimestamp': prepared_page['base_timestamp'],
                      'starttimestamp': prepared_page['start_timestamp'],
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
                del self.prepared_pages[title] # this must be outdated now
                return CommandEditConflict(command_pending.id, command_pending.command)
            elif e.code == 'protectedpage':
                return CommandPageProtected(command_pending.id, command_pending.command, curtimestamp=prepared_page['start_timestamp'])
            elif e.code == 'maxlag':
                retry_after_seconds = 5 # the API returns this in a Retry-After header, but mwapi hides that from us :(
                retry_after = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=retry_after_seconds)
                retry_after = retry_after.replace(microsecond=0)
                return CommandMaxlagExceeded(command_pending.id, command_pending.command, retry_after)
            elif e.code == 'blocked' or e.code == 'autoblocked':
                auto = e.code == 'autoblocked'
                blockinfo = None # the API returns this in a 'blockinfo' member of the 'error' object, but mwapi hides that from us :(
                return CommandBlocked(command_pending.id, command_pending.command, auto, blockinfo)
            elif e.code == 'readonly':
                reason = None # the API returns this in a 'readonlyreason' member of the 'error' object, but mwapi hides that from us :(
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
            del self.prepared_pages[title] # this must be outdated now, otherwise we would’ve detected the no-op before trying to edit
            return CommandNoop(command_pending.id, command_pending.command, prepared_page['base_revid'])

        assert response['edit']['oldrevid'] == prepared_page['base_revid']
        del self.prepared_pages[title] # this must be outdated now, and we don’t know the new wikitext since non-conflicting edits may have been merged
        return CommandEdit(command_pending.id, command_pending.command, response['edit']['oldrevid'], response['edit']['newrevid'])
