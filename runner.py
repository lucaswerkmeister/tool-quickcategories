import datetime
import mwapi # type: ignore
from typing import Dict, List, Optional

from command import CommandPlan, CommandFinish, CommandEdit, CommandNoop, CommandPageMissing, CommandEditConflict, CommandMaxlagExceeded, CommandBlocked
import siteinfo


class Runner():

    def __init__(self, session: mwapi.Session, summary_suffix: Optional[str] = None):
        self.session = session
        self.csrf_token = session.get(action='query',
                                      meta='tokens')['query']['tokens']['csrftoken']
        self.summary_suffix = summary_suffix
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
            revision = page['revisions'][0]
            slot = revision['slots']['main']
            if slot['contentmodel'] != 'wikitext' or slot['contentformat'] != 'text/x-wiki':
                raise ValueError('Unexpected content model or format for revision %d of page %s, refusing to edit!' % (revision['revid'], title))
            original_wikitext = slot['content']
            self.prepared_pages[title] = {
                'wikitext': slot['content'],
                'page_id': page['pageid'],
                'base_timestamp': revision['timestamp'],
                'base_revid': revision['revid'],
                'start_timestamp': response['curtimestamp'],
            }

        for normalization in response['query'].get('normalized', {}):
            self.prepared_pages[normalization['from']] = self.prepared_pages[normalization['to']]

    def run_command(self, plan: CommandPlan) -> CommandFinish:
        title = plan.command.page
        if title not in self.prepared_pages:
            self.prepare_pages([title])
        prepared_page = self.prepared_pages[title]
        category_info = siteinfo.category_info(self.session)

        if 'missing' in prepared_page:
            return CommandPageMissing(plan.id, plan.command, curtimestamp=prepared_page['curtimestamp'])

        wikitext, actions = plan.command.apply(prepared_page['wikitext'], category_info)
        summary = ''
        for action, noop in actions:
            action_summary = action.summary(category_info)
            if noop:
                action_summary = siteinfo.parentheses(self.session, action_summary)
            if summary:
                summary += siteinfo.comma_separator(self.session)
            summary += action_summary

        if self.summary_suffix:
            summary += siteinfo.semicolon_separator(self.session)
            summary += self.summary_suffix

        if wikitext == prepared_page['wikitext']:
            return CommandNoop(plan.id, plan.command, prepared_page['base_revid'])
        try:
            response = self.session.post(**{'action': 'edit',
                                            'pageid': prepared_page['page_id'],
                                            'text': wikitext,
                                            'summary': summary,
                                            'bot': True,
                                            'basetimestamp': prepared_page['base_timestamp'],
                                            'starttimestamp': prepared_page['start_timestamp'],
                                            'contentformat': 'text/x-wiki',
                                            'contentmodel': 'wikitext',
                                            'token': self.csrf_token,
                                            'assert': 'user', # assert is a keyword, can’t use kwargs syntax :(
                                            'maxlag': 5,
                                            'formatversion': 2})
        except mwapi.errors.APIError as e:
            if e.code == 'editconflict':
                del self.prepared_pages[title] # this must be outdated now
                return CommandEditConflict(plan.id, plan.command)
            elif e.code == 'maxlag':
                retry_after_seconds = 5 # the API returns this in a Retry-After header, but mwapi hides that from us :(
                retry_after = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=retry_after_seconds)
                return CommandMaxlagExceeded(plan.id, plan.command, retry_after)
            elif e.code == 'blocked' or e.code == 'autoblocked':
                auto = e.code == 'autoblocked'
                blockinfo = None # the API returns this in a 'blockinfo' member of the 'error' object, but mwapi hides that from us :(
                return CommandBlocked(plan.id, plan.command, auto, blockinfo)
            else:
                raise e
        assert response['edit']['oldrevid'] == prepared_page['base_revid']
        return CommandEdit(plan.id, plan.command, response['edit']['oldrevid'], response['edit']['newrevid'])
