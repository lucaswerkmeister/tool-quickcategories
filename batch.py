from typing import Any, List


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

    def __eq__(self, value: Any) -> bool:
        return type(value) is Command and \
            self.page == value.page and \
            self.actions == value.actions

    def __str__(self) -> str:
        return '|'.join([self.page, *[str(action) for action in self.actions]])

    def __repr__(self) -> str:
        return 'Command(' + repr(self.page) + ', ' + repr(self.actions) + ')'


class Action:
    """A transformation to a piece of wikitext."""
    pass


class CategoryAction(Action):
    """An action to modify a category in the wikitext of a page."""

    def __init__(self, category: str):
        assert category, 'category should not be empty'
        assert not category.startswith('Category:'), 'category should not include namespace'
        assert '[' not in category, 'category should not be a wikilink'
        assert ']' not in category, 'category should not be a wikilink'
        self.category = category
        super().__init__()


class AddCategoryAction(CategoryAction):
    """An action to add a category to the wikitext of a page."""

    def __eq__(self, value: Any) -> bool:
        return type(value) is AddCategoryAction and \
            self.category == value.category

    def __str__(self) -> str:
        return '+Category:' + self.category

    def __repr__(self) -> str:
        return 'AddCategoryAction(' + repr(self.category) + ')'


class RemoveCategoryAction(CategoryAction):
    """An action to remove a category from the wikitext of a page."""

    def __eq__(self, value: Any) -> bool:
        return type(value) is RemoveCategoryAction and \
            self.category == value.category

    def __str__(self) -> str:
        return '-Category:' + self.category

    def __repr__(self) -> str:
        return 'RemoveCategoryAction(' + repr(self.category) + ')'
