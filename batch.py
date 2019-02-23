import mwapi # type: ignore
import mwparserfromhell # type: ignore
from typing import Any, List, Tuple

import siteinfo


class Batch:
    """A list of commands to be performed for one user."""

    def __init__(self, authentication: dict, commands: List['Command']):
        self.authentication = authentication
        self.commands = commands

    def __eq__(self, value: Any) -> bool:
        return type(value) is Batch and \
            self.authentication == value.authentication and \
            self.commands == value.commands

    def __str__(self) -> str:
        return '\n'.join([str(command) for command in self.commands])

    def __repr__(self) -> str:
        return 'Batch(' + repr(self.authentication) + ', ' + repr(self.commands) + ')'


class Command:
    """A list of actions to perform on a page."""

    def __init__(self, page: str, actions: List['Action']):
        self.page = page
        self.actions = actions

    def run(self, session: mwapi.Session):
        response = session.get(action='query',
                               titles=[self.page],
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
            raise ValueError('Unexpected content model or format for revision %d of page %s, refusing to edit!' % (revision['revid'], self.page))
        original_wikitext = slot['content']
        wikitext = original_wikitext
        summary = ''
        category_info = siteinfo.category_info(session)

        for action in self.actions:
            new_wikitext = action.apply(wikitext, category_info)
            action_summary = action.summary(category_info)
            if wikitext == new_wikitext:
                action_summary = siteinfo.parentheses(session, action_summary)
            if summary:
                summary += siteinfo.comma_separator(session)
            summary += action_summary
            wikitext = new_wikitext

        if wikitext == original_wikitext:
            return
        token = session.get(action='query',
                            meta='tokens')['query']['tokens']['csrftoken']
        session.post(action='edit',
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

    def __eq__(self, value: Any) -> bool:
        return type(value) is Command and \
            self.page == value.page and \
            self.actions == value.actions

    def __str__(self) -> str:
        return self.page + '|' + '|'.join([str(action) for action in self.actions])

    def __repr__(self) -> str:
        return 'Command(' + repr(self.page) + ', ' + repr(self.actions) + ')'


class Action:
    """A transformation to a piece of wikitext."""

    def apply(self, wikitext: str, category_info: Tuple[str, List[str]]) -> str:
        raise NotImplementedError

    def summary(self, category_info: Tuple[str, List[str]]) -> str:
        raise NotImplementedError


class CategoryAction(Action):
    """An action to modify a category in the wikitext of a page."""

    symbol = ''

    def __init__(self, category: str):
        assert category, 'category should not be empty'
        assert not category.startswith('Category:'), 'category should not include namespace'
        assert '[' not in category, 'category should not be a wikilink'
        assert ']' not in category, 'category should not be a wikilink'
        self.category = category
        super().__init__()

    def _is_category(self, wikilink: mwparserfromhell.nodes.wikilink.Wikilink, category_info: Tuple[str, List[str]]) -> bool:
        for category_namespace_name in category_info[1]:
            if wikilink.startswith('[[' + category_namespace_name + ':'):
                return True
        return False

    def summary(self, category_info: Tuple[str, List[str]]) -> str:
        return type(self).symbol + '[[' + category_info[0] + ':' + self.category + ']]'

    def __eq__(self, value: Any) -> bool:
        return type(self) is type(value) and \
            self.category == value.category

    def __str__(self) -> str:
        return type(self).symbol + 'Category:' + self.category


class AddCategoryAction(CategoryAction):
    """An action to add a category to the wikitext of a page."""

    symbol = '+'

    def apply(self, wikitext: str, category_info: Tuple[str, List[str]]) -> str:
        wikicode = mwparserfromhell.parse(wikitext)
        last_category = None
        for wikilink in wikicode.ifilter_wikilinks():
            if not self._is_category(wikilink, category_info):
                continue
            if wikilink.title.split(':', 1)[1] == self.category:
                return wikitext
            last_category = wikilink
        wikilink = mwparserfromhell.nodes.wikilink.Wikilink(category_info[0] + ':' + self.category)
        if last_category:
            wikicode.insert_after(last_category, wikilink)
            wikicode.insert_before(wikilink, '\n')
        else:
            if wikicode:
                wikicode.append('\n')
            wikicode.append(wikilink)
        return str(wikicode)

    def __repr__(self) -> str:
        return 'AddCategoryAction(' + repr(self.category) + ')'


class RemoveCategoryAction(CategoryAction):
    """An action to remove a category from the wikitext of a page."""

    symbol = '-'

    def apply(self, wikitext: str, category_info: Tuple[str, List[str]]) -> str:
        wikicode = mwparserfromhell.parse(wikitext)
        for index, wikilink in enumerate(wikicode.nodes):
            if not isinstance(wikilink, mwparserfromhell.nodes.wikilink.Wikilink):
                continue
            if not self._is_category(wikilink, category_info):
                continue
            if wikilink.title.split(':', 1)[1] == self.category:
                # also remove preceding line break
                if index-1 >= 0 and \
                   isinstance(wikicode.nodes[index-1], mwparserfromhell.nodes.text.Text) and \
                   wikicode.nodes[index-1].value.endswith('\n'):
                    wikicode.nodes[index-1].value = wikicode.nodes[index-1].value[:-1]
                # or following line break
                elif index+1 < len(wikicode.nodes) and \
                   isinstance(wikicode.nodes[index+1], mwparserfromhell.nodes.text.Text) and \
                   wikicode.nodes[index+1].value.startswith('\n'):
                    wikicode.nodes[index+1].value = wikicode.nodes[index+1].value[1:]
                del wikicode.nodes[index] # this should happen *after* the above blocks, otherwise the indices get confusing
                break
        return str(wikicode)

    def __repr__(self) -> str:
        return 'RemoveCategoryAction(' + repr(self.category) + ')'
