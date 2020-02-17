from localuser import LocalUser


localUser1 = LocalUser('Lucas Werkmeister', 'www.wikidata.org', 2794369, 46054761)
localUser2 = LocalUser('Lucas Werkmeister', 'commons.wikimedia.org', 6198807, 46054761)


def test_LocalUser_eq_same() -> None:
    assert localUser1 == localUser1

def test_LocalUser_eq_equal() -> None:
    assert localUser1 == LocalUser('Lucas Werkmeister', 'www.wikidata.org', 2794369, 46054761)

def test_LocalUser_eq_different_type() -> None:
    assert localUser1 != 'Lucas Werkmeister'
    assert localUser1 != 2794369

def test_LocalUser_eq_different_user_name() -> None:
    # still considered equal
    assert localUser1 == LocalUser('Lucas Werkmeister (renamed)', 'www.wikidata.org', 2794369, 46054761)

def test_LocalUser_eq_different_domain() -> None:
    assert localUser1 != LocalUser('Lucas Werkmeister', 'commons.wikimedia.org', 2794369, 46054761)

def test_LocalUser_eq_different_local_user_id() -> None:
    assert localUser1 != LocalUser('Lucas Werkmeister', 'www.wikidata.org', 27943690, 46054761)

def test_LocalUser_eq_different_global_user_id() -> None:
    assert localUser1 != LocalUser('Lucas Werkmeister', 'www.wikidata.org', 2794369, 460547610)

def test_LocalUser_str() -> None:
    assert str(localUser1) == 'Lucas Werkmeister@www.wikidata.org'

def test_LocalUser_repr() -> None:
    assert eval(repr(localUser1)) == localUser1
