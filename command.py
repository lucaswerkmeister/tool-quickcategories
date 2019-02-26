from typing import Any, List, Tuple

from action import Action

class Command:
    """A list of actions to perform on a page."""

    def __init__(self, page: str, actions: List['Action']):
        self.page = page
        self.actions = actions

    def apply(self, wikitext: str, category_info: Tuple[str, List[str]]) -> Tuple[str, List[Tuple[Action, bool]]]:
        """Apply the actions of this command to the given wikitext and return
        the result as well as the actions together with the
        information whether they were a no-op or not.
        """
        actions = []

        for action in self.actions:
            new_wikitext = action.apply(wikitext, category_info)
            actions.append((action, wikitext == new_wikitext))
            wikitext = new_wikitext

        return wikitext, actions

    def __eq__(self, value: Any) -> bool:
        return type(value) is Command and \
            self.page == value.page and \
            self.actions == value.actions

    def __str__(self) -> str:
        return self.page + '|' + '|'.join([str(action) for action in self.actions])

    def __repr__(self) -> str:
        return 'Command(' + repr(self.page) + ', ' + repr(self.actions) + ')'
