import mwapi # type: ignore
import requests
from typing import Dict, Optional, Sequence, Tuple, Union

import sitematrix


def load_pagepile(session: mwapi.Session, id: int) -> Optional[Tuple[str, Sequence[str]]]:
    try:
        params = {'id': id,
                  'action': 'get_data',
                  'format': 'json'} # type: Dict[str, Union[int, str]]
        r = requests.get('https://tools.wmflabs.org/pagepile/api.php', params=params)
        pile = r.json()
    except ValueError:
        # PagePile doesn’t properly catch most errors, it just dumps them to the output, producing invalid JSON
        # we simply treat them all as “no such pile”
        return None
    domain = sitematrix.dbname_to_domain(session, pile['wiki'])
    pages = [page.replace('_', ' ') for page in pile['pages']]
    return domain, pages
