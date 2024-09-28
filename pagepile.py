from collections.abc import Iterable, Sequence
import mwapi  # type: ignore
import requests
from typing import Optional

import sitematrix


def load_pagepile(session: mwapi.Session, id: int | str) -> Optional[tuple[str, Sequence[str]]]:
    try:
        params: dict[str, int | str] = {'id': str(id),
                                        'action': 'get_data',
                                        'format': 'json'}
        r = requests.get('https://pagepile.toolforge.org/api.php', params=params)
        pile = r.json()
    except ValueError:
        # PagePile doesn’t properly catch most errors, it just dumps them to the output, producing invalid JSON
        # we simply treat them all as “no such pile”
        return None
    domain = sitematrix.dbname_to_domain(session, pile['wiki'])
    pages = [page.replace('_', ' ') for page in pile['pages']]
    return domain, pages


def create_pagepile(session: mwapi.Session, domain: str, pages: Iterable[str]) -> int:
    r = requests.post('https://pagepile.toolforge.org/api.php', data={
        'action': 'create_pile_with_data',
        'wiki': sitematrix.domain_to_dbname(session, domain),
        'data': '\n'.join([page + '\t-999'  # -999 means “detect namespace” to PagePile::addPage(), default would force main namespace
                           for page in pages]),
    })
    return r.json()['pile']['id']
