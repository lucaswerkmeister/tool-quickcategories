import mwapi # type: ignore

from command import CommandPlan, CommandFinish, CommandEdit, CommandNoop
import siteinfo


class Runner():

    def run_command(self, plan: CommandPlan, session: mwapi.Session) -> CommandFinish:
        response = session.get(action='query',
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
        category_info = siteinfo.category_info(session)

        wikitext, actions = plan.command.apply(original_wikitext, category_info)
        summary = ''
        for action, noop in actions:
            action_summary = action.summary(category_info)
            if noop:
                action_summary = siteinfo.parentheses(session, action_summary)
            if summary:
                summary += siteinfo.comma_separator(session)
            summary += action_summary

        if wikitext == original_wikitext:
            return CommandNoop(plan.id, plan.command, revision['revid'])
        token = session.get(action='query',
                            meta='tokens')['query']['tokens']['csrftoken']
        response = session.post(action='edit',
                                pageid=page['pageid'],
                                text=wikitext,
                                summary=summary,
                                bot=True,
                                basetimestamp=revision['timestamp'],
                                starttimestamp=response['curtimestamp'],
                                contentformat='text/x-wiki',
                                contentmodel='wikitext',
                                token=token,
                                formatversion=2)
        assert response['edit']['oldrevid'] == revision['revid']
        return CommandEdit(plan.id, plan.command, response['edit']['oldrevid'], response['edit']['newrevid'])
