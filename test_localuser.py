from localuser import LocalUser


localUser1 = LocalUser('Lucas Werkmeister', 'www.wikidata.org', 2794369, 46054761)
localUser2 = LocalUser('Lucas Werkmeister', 'commons.wikimedia.org', 6198807, 46054761)


def test_LocalUser_str() -> None:
    assert str(localUser1) == 'Lucas Werkmeister@www.wikidata.org'
