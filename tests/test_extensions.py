import pytest

from fastdl.routes import Suffix


@pytest.mark.parametrize('extensions,path', [
    (('.bsp', '.nav'), 'maps/a.bsp'),
    (('.bsp', '.nav'), 'maps/a.bsp.bz2'),
    (('.bsp', '.nav'), 'maps/sub/a.nav'),
    (('.bsp', '.nav'), 'maps/sub/a.nav.bz2'),
    (('.vmt', '.vtf'), 'materials/m.vmt'),
    (('.vmt', '.vtf'), 'materials/m.vtf.bz2'),
    (('.mdl', '.phy', '.vmt', '.vtf', '.vtx', '.vvd'), 'models/m.mdl'),
    (('.txt',), 'scripts/items/i.txt.bz2'),
    (('.vcs',), 'shaders/s.vcs'),
    (('.mp3', '.wav'), 'sound/s.wav'),
])
def test_allowed_extensions_match(extensions, path):
    assert Suffix(*extensions)(path)


def test_single_extension_allowed():
    assert Suffix('.bsp')('maps/x/y.bsp')
    assert Suffix('.bsp')('maps/x/y.bsp.bz2')


def test_extension_must_be_suffix_true_positive():
    assert not Suffix('.bsp')('maps/evil.bsp.exe')
    assert not Suffix('.bsp')('maps/evil.bsp.txt')
    assert not Suffix('.bsp')('maps/evil.bsp/bad.vmt')


def test_extension_case_sensitive():
    assert not Suffix('.bsp')('maps/ARENA.BSP')


def test_double_extension_cannot_disguise():
    assert not Suffix('.bsp')('maps/m.bsp.bz2.sh')


def test_uppercase_url_rejected(client):
    response = client.get('/test/maps/foolish/ARENA.BSP')
    assert response.status_code == 422


def test_extra_extension_rejected(client):
    response = client.get('/test/maps/foolish/arena.bsp.txt')
    assert response.status_code == 422


def test_listing_only_shows_allowed_files(client):
    response = client.get('/test/maps/de_test/')
    assert response.status_code == 200
    assert 'de_dust.bsp' in response.text
    assert 'de_dust.bsp.bz2' in response.text
    assert 'huge.bsp' in response.text
    assert 'notes.txt' not in response.text