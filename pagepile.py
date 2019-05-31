import json
import mwapi # type: ignore
from typing import Optional, Tuple, Sequence
import urllib.request

import sitematrix


def load_pagepile(session: mwapi.Session, id: int) -> Optional[Tuple[str, Sequence[str]]]:
    url = 'https://tools.wmflabs.org/pagepile/api.php?id=%d&action=get_data&format=json' % id
    try:
        pile = json.load(urllib.request.urlopen(url))
    except json.decoder.JSONDecodeError:
        # PagePile doesn’t properly catch most errors, it just dumps them to the output
        # we simply treat them all as “no such pile”
        return None
    domain = sitematrix.dbname_to_domain(session, pile['wiki'])
    pages = [page.replace('_', ' ') for page in pile['pages']]
    return domain, pages
