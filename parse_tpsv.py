"""Functions to parse batches from tab/pipe-separated values syntax."""

from typing import List, Optional

from action import Action, AddCategoryAction, AddCategoryWithSortKeyAction, AddCategoryProvideSortKeyAction, AddCategoryReplaceSortKeyAction, RemoveCategoryAction, RemoveCategoryWithSortKeyAction
from batch import NewBatch
from command import Command
from page import Page


def parse_batch(tpsv: str, title: Optional[str]) -> NewBatch:
    commands = []
    errors = []
    for line in tpsv.split('\n'):
        line = line.rstrip('\r')
        if not line:
            continue
        try:
            commands.append(parse_command(line))
        except Exception as e:
            errors.append(e)
    if errors:
        raise ParseBatchError(errors)
    return NewBatch(commands, title)


def parse_command(line: str) -> Command:
    [title, *other_fields] = [field.strip() for field in line.replace('\t', '|').split('|')]
    if not other_fields:
        raise ValueError("no actions for page '%s'" % title)
    page = Page(title)
    actions = []
    errors = []
    for field in other_fields:
        try:
            actions.append(parse_action(field))
        except Exception as e:
            errors.append(e)
    if errors:
        raise ParseCommandError(page, errors)
    return Command(page, actions)


def parse_action(field: str) -> Action:
    if field.startswith('+Category:'):
        title_and_sort_key = field[10:].split('#', maxsplit=1)
        if len(title_and_sort_key) == 1:
            title = title_and_sort_key[0]
            return AddCategoryAction(title)
        [title, sort_key] = title_and_sort_key
        if sort_key.startswith('###'):
            raise ValueError('too many #s')
        if sort_key.startswith('##'):
            return AddCategoryReplaceSortKeyAction(title, sort_key[2:] or None)
        if sort_key.startswith('#'):
            return AddCategoryProvideSortKeyAction(title, sort_key[1:] or None)
        return AddCategoryWithSortKeyAction(title, sort_key or None)
    elif field.startswith('-Category:'):
        title_and_sort_key = field[10:].split('#', maxsplit=1)
        if len(title_and_sort_key) == 1:
            title = title_and_sort_key[0]
            return RemoveCategoryAction(title)
        [title, sort_key] = title_and_sort_key
        if sort_key.startswith('#'):
            raise ValueError('too many #s')
        return RemoveCategoryWithSortKeyAction(title, sort_key)
    else:
        raise ValueError("invalid field '%s'" % field)


class ParseBatchError(ValueError):

    def __init__(self, errors: List[Exception]):
        self.errors = errors
        super().__init__('errors parsing batch: %s' % '; '.join(map(str, errors)))


class ParseCommandError(ValueError):

    def __init__(self, page: Page, errors: List[Exception]):
        self.page = page
        self.errors = errors
        super().__init__("errors parsing command for page '%s': %s" % (str(page), ', '.join(map(str, errors))))
