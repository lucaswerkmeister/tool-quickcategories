"""Functions to parse batches from tab/pipe-separated values syntax."""

from typing import List, Optional

from action import Action, AddCategoryAction, RemoveCategoryAction
from batch import NewBatch
from command import Command


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
    [page, *other_fields] = [field.strip() for field in line.replace('\t', '|').split('|')]
    if not other_fields:
        raise ValueError("no actions for page '%s'" % page)
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
        return AddCategoryAction(field[10:])
    elif field.startswith('-Category:'):
        return RemoveCategoryAction(field[10:])
    else:
        raise ValueError("invalid field '%s'" % field)


class ParseBatchError(ValueError):

    def __init__(self, errors: List[Exception]):
        self.errors = errors
        super().__init__('errors parsing batch: %s' % '; '.join(map(str, errors)))


class ParseCommandError(ValueError):

    def __init__(self, page: str, errors: List[Exception]):
        self.page = page
        self.errors = errors
        super().__init__("errors parsing command for page '%s': %s" % (page, ', '.join(map(str, errors))))
