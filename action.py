import mwparserfromhell  # type: ignore
from mwparserfromhell.nodes.wikilink import Wikilink  # type: ignore
from typing import Any, Union

from siteinfo import CategoryInfo


class Action:
    """A transformation to a piece of wikitext."""

    def apply(self, wikitext: str, category_info: CategoryInfo) -> str:
        raise NotImplementedError

    def summary(self, category_info: CategoryInfo) -> str:
        raise NotImplementedError

    def is_minor(self) -> bool:
        """Whether this action, on its own, can be considered a minor edit."""
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

    def _is_category(self, wikilink: Wikilink, category_info: CategoryInfo) -> bool:
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
            if self._accept_category_link(wikilink, category_info):
                return str(wikicode)
            last_category = wikilink
        wikilink = self._make_category_link(category_info)
        if last_category:
            wikicode.insert_after(last_category, wikilink)
            wikicode.insert_before(wikilink, '\n')
        else:
            if wikicode:
                wikicode.append('\n')
            wikicode.append(wikilink)
        return str(wikicode)

    def _accept_category_link(self, wikilink: Wikilink, category_info: CategoryInfo) -> bool:
        return self._same_category(wikilink.title.split(':', 1)[1], self.category, category_info)

    def _make_category_link(self, category_info: CategoryInfo) -> Wikilink:
        return Wikilink(category_info[0] + ':' + self.category)

    def is_minor(self) -> bool:
        return True

    def __repr__(self) -> str:
        return 'AddCategoryAction(' + repr(self.category) + ')'


class AddCategoryAndSortKeyAction(AddCategoryAction):
    """An action to add a category to the wikitext of a page, including a sort key."""

    sort_key_symbol = ''

    def __init__(self, category: str, sort_key: Union[str, None]):
        assert sort_key != '', 'sort key cannot be the empty string'
        self.sort_key = sort_key
        super().__init__(category)

    def summary(self, category_info: CategoryInfo) -> str:
        return '+[[' + category_info[0] + ':' + self.category + '|' + \
            category_info[0] + ':' + self.category + '|' + (self.sort_key or '') + ']]'

    def __eq__(self, value: Any) -> bool:
        return type(self) is type(value) and \
            self.category == value.category and \
            self.sort_key == value.sort_key

    def __str__(self) -> str:
        return super().__str__() + type(self).sort_key_symbol + (self.sort_key or '')


class AddCategoryWithSortKeyAction(AddCategoryAndSortKeyAction):
    """An action to add a category with a certain sort key to the wikitext of a page.

    If no category link for that category exists yet, it is added with that sort key.
    If such a category link exists, with or without any sort key, no change is made."""

    sort_key_symbol = '#'

    def _make_category_link(self, category_info: CategoryInfo) -> Wikilink:
        if not self.sort_key:
            return super()._make_category_link(category_info)
        return Wikilink(category_info[0] + ':' + self.category,
                        self.sort_key)

    def __repr__(self) -> str:
        return 'AddCategoryWithSortKeyAction(' + \
            repr(self.category) + ', ' + \
            repr(self.sort_key) + ')'


class AddCategoryProvideSortKeyAction(AddCategoryAndSortKeyAction):
    """An action to provide a category with a certain sort key in the wikitext of a page.

    If no category link for that category exists yet, it is added with that sort key.
    If such a category link exists, but without a sort key, the sort key is added.
    If the existing category specifies a different sort key, no change is made."""

    sort_key_symbol = '##'

    def _accept_category_link(self, wikilink: Wikilink, category_info: CategoryInfo) -> bool:
        if super()._accept_category_link(wikilink, category_info):
            if wikilink.text is None:
                wikilink.text = self.sort_key
            return True
        else:
            return False

    def _make_category_link(self, category_info: CategoryInfo) -> Wikilink:
        if not self.sort_key:
            return super()._make_category_link(category_info)
        return Wikilink(category_info[0] + ':' + self.category,
                        self.sort_key)

    def __repr__(self) -> str:
        return 'AddCategoryProvideSortKeyAction(' + \
            repr(self.category) + ', ' + \
            repr(self.sort_key) + ')'


class AddCategoryReplaceSortKeyAction(AddCategoryAndSortKeyAction):
    """An action to replace a category’s sort key in the wikitext of a page.

    If no category link for that category exists yet, it is added with that sort key.
    If such a category link exists, with or without any sort key, its sort key is replaced with the given one."""

    sort_key_symbol = '###'

    def _accept_category_link(self, wikilink: Wikilink, category_info: CategoryInfo) -> bool:
        if super()._accept_category_link(wikilink, category_info):
            wikilink.text = self.sort_key
            return True
        else:
            return False

    def _make_category_link(self, category_info: CategoryInfo) -> Wikilink:
        return Wikilink(category_info[0] + ':' + self.category,
                        self.sort_key)

    def __repr__(self) -> str:
        return 'AddCategoryReplaceSortKeyAction(' + \
            repr(self.category) + ', ' + \
            repr(self.sort_key) + ')'


class RemoveCategoryAction(CategoryAction):
    """An action to remove a category from the wikitext of a page."""

    symbol = '-'

    def apply(self, wikitext: str, category_info: CategoryInfo) -> str:
        wikicode = mwparserfromhell.parse(wikitext)
        for index, wikilink in enumerate(wikicode.nodes):
            if not isinstance(wikilink, Wikilink):
                continue
            if not self._is_category(wikilink, category_info):
                continue
            if self._reject_category_link(wikilink, category_info):
                # also remove preceding line break
                if index-1 >= 0 and \
                   isinstance(wikicode.nodes[index-1], mwparserfromhell.nodes.text.Text) and \
                   wikicode.nodes[index-1].value.endswith('\n'):
                    wikicode.nodes[index-1].value = wikicode.nodes[index-1].value[:-1]
                # or following line break
                elif (index+1 < len(wikicode.nodes) and
                      isinstance(wikicode.nodes[index+1], mwparserfromhell.nodes.text.Text) and
                      wikicode.nodes[index+1].value.startswith('\n')):
                    wikicode.nodes[index+1].value = wikicode.nodes[index+1].value[1:]
                del wikicode.nodes[index]  # this should happen *after* the above blocks, otherwise the indices get confusing
                break
        return str(wikicode)

    def _reject_category_link(self, wikilink: Wikilink, category_info: CategoryInfo) -> bool:
        return self._same_category(wikilink.title.split(':', 1)[1], self.category, category_info)

    def is_minor(self) -> bool:
        return False

    def __repr__(self) -> str:
        return 'RemoveCategoryAction(' + repr(self.category) + ')'


class RemoveCategoryWithSortKeyAction(RemoveCategoryAction):
    """An action to remove a category from the wikitext of a page if it matches a certain sort key."""

    def __init__(self, category: str, sort_key: Union[str, None]):
        assert sort_key != '', 'sort key cannot be the empty string'
        self.sort_key = sort_key
        super().__init__(category)

    def _reject_category_link(self, wikilink: Wikilink, category_info: CategoryInfo) -> bool:
        return super()._reject_category_link(wikilink, category_info) and \
            wikilink.text == self.sort_key

    def summary(self, category_info: CategoryInfo) -> str:
        return '-[[' + category_info[0] + ':' + self.category + '|' + \
            category_info[0] + ':' + self.category + '|' + (self.sort_key or '') + ']]'

    def __eq__(self, value: Any) -> bool:
        return type(self) is type(value) and \
            self.category == value.category and \
            self.sort_key == value.sort_key

    def __str__(self) -> str:
        return super().__str__() + '#' + (self.sort_key or '')

    def __repr__(self) -> str:
        return 'RemoveCategoryWithSortKeyAction(' + \
            repr(self.category) + ', ' + \
            repr(self.sort_key) + ')'
