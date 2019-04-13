from localuser import LocalUser


localUser1 = LocalUser('Lucas Werkmeister', 'www.wikidata.org', 2794369, 46054761)


def test_LocalUser_eq_same():
    assert localUser1 == localUser1

def test_LocalUser_eq_equal():
    assert localUser1 == LocalUser('Lucas Werkmeister', 'www.wikidata.org', 2794369, 46054761)

def test_LocalUser_eq_different_type():
    assert localUser1 != 'Lucas Werkmeister'
    assert localUser1 != 2794369

def test_LocalUser_eq_different_user_name():
    # still considered equal
    assert localUser1 == LocalUser('Lucas Werkmeister (renamed)', 'www.wikidata.org', 2794369, 46054761)

def test_LocalUser_eq_different_domain():
    assert localUser1 != LocalUser('Lucas Werkmeister', 'commons.wikimedia.org', 2794369, 46054761)

def test_LocalUser_eq_different_local_user_id():
    assert localUser1 != LocalUser('Lucas Werkmeister', 'www.wikidata.org', 27943690, 46054761)

def test_LocalUser_eq_different_global_user_id():
    assert localUser1 != LocalUser('Lucas Werkmeister', 'www.wikidata.org', 2794369, 460547610)

def test_LocalUser_str():
    assert str(localUser1) == 'Lucas Werkmeister@www.wikidata.org'

def test_LocalUser_repr():
    assert eval(repr(localUser1)) == localUser1
