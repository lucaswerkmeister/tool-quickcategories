import mwapi # type: ignore

from command import CommandPlan, CommandFinish, CommandEdit, CommandNoop
import siteinfo


class Runner():

    def __init__(self, session: mwapi.Session):
        self.session = session
        self.csrf_token = session.get(action='query',
                                      meta='tokens')['query']['tokens']['csrftoken']

    def run_command(self, plan: CommandPlan) -> CommandFinish:
        response = self.session.get(action='query',
                                    titles=[plan.command.page],
                                    prop=['revisions'],
                                    rvprop=['ids', 'content', 'contentmodel', 'timestamp'],
                                    rvslots=['main'],
                                    rvlimit=1,
                                    curtimestamp=True,
                                    formatversion=2)
        page = response['query']['pages'][0]
        revision = page['revisions'][0]
        slot = revision['slots']['main']
        if slot['contentmodel'] != 'wikitext' or slot['contentformat'] != 'text/x-wiki':
            raise ValueError('Unexpected content model or format for revision %d of page %s, refusing to edit!' % (revision['revid'], plan.command.page))
        original_wikitext = slot['content']
        category_info = siteinfo.category_info(self.session)

        wikitext, actions = plan.command.apply(original_wikitext, category_info)
        summary = ''
        for action, noop in actions:
            action_summary = action.summary(category_info)
            if noop:
                action_summary = siteinfo.parentheses(self.session, action_summary)
            if summary:
                summary += siteinfo.comma_separator(self.session)
            summary += action_summary

        if wikitext == original_wikitext:
            return CommandNoop(plan.id, plan.command, revision['revid'])
        response = self.session.post(**{'action': 'edit',
                                        'pageid': page['pageid'],
                                        'text': wikitext,
                                        'summary': summary,
                                        'bot': True,
                                        'basetimestamp': revision['timestamp'],
                                        'starttimestamp': response['curtimestamp'],
                                        'contentformat': 'text/x-wiki',
                                        'contentmodel': 'wikitext',
                                        'token': self.csrf_token,
                                        'assert': 'user', # assert is a keyword, can’t use kwargs syntax :(
                                        'formatversion': 2})
        assert response['edit']['oldrevid'] == revision['revid']
        return CommandEdit(plan.id, plan.command, response['edit']['oldrevid'], response['edit']['newrevid'])
