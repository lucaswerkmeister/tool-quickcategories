import mwparserfromhell # type: ignore
from typing import Any

from siteinfo import CategoryInfo


class Action:
    """A transformation to a piece of wikitext."""

    def apply(self, wikitext: str, category_info: CategoryInfo) -> str:
        raise NotImplementedError

    def summary(self, category_info: CategoryInfo) -> str:
        raise NotImplementedError

    def cleanup(self) -> None:
        """Partially normalize the action, as a convenience for users.

        This should not be used as a replacement for full
        normalization via the MediaWiki API.
        """
        pass


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

    def _is_category(self, wikilink: mwparserfromhell.nodes.wikilink.Wikilink, category_info: CategoryInfo) -> bool:
        for category_namespace_name in category_info[1]:
            if wikilink.startswith('[[' + category_namespace_name + ':'):
                return True
        return False

    def _same_category(self, category1: str, category2: str, category_info: CategoryInfo) -> bool:
        if category_info[2] == 'first-letter':
            category1 = category1[:1].upper() + category1[1:]
            category2 = category2[:1].upper() + category2[1:]
        elif category_info[2] == 'case-sensitive':
            pass
        else:
            raise ValueError('Unknown case handling %s' % category_info[2])

        return category1.replace(' ', '_') == category2.replace(' ', '_')

    def summary(self, category_info: CategoryInfo) -> str:
        return type(self).symbol + '[[' + category_info[0] + ':' + self.category + ']]'

    def cleanup(self) -> None:
        self.category = self.category.replace('_', ' ')

    def __eq__(self, value: Any) -> bool:
        return type(self) is type(value) and \
            self.category == value.category

    def __str__(self) -> str:
        return type(self).symbol + 'Category:' + self.category


class AddCategoryAction(CategoryAction):
    """An action to add a category to the wikitext of a page."""

    symbol = '+'

    def apply(self, wikitext: str, category_info: CategoryInfo) -> str:
        wikicode = mwparserfromhell.parse(wikitext)
        last_category = None
        for wikilink in wikicode.ifilter_wikilinks():
            if not self._is_category(wikilink, category_info):
                continue
            if self._same_category(wikilink.title.split(':', 1)[1], self.category, category_info):
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

    def apply(self, wikitext: str, category_info: CategoryInfo) -> str:
        wikicode = mwparserfromhell.parse(wikitext)
        for index, wikilink in enumerate(wikicode.nodes):
            if not isinstance(wikilink, mwparserfromhell.nodes.wikilink.Wikilink):
                continue
            if not self._is_category(wikilink, category_info):
                continue
            if self._same_category(wikilink.title.split(':', 1)[1], self.category, category_info):
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
