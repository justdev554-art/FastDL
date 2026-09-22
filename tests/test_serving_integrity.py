import bz2

import pytest


def test_plain_file_served_verbatim(client):
    response = client.get('/test/maps/foolish/arena.bsp')
    assert response.status_code == 200
    assert response.content == b'ARENA-BSP'
    assert response.headers['content-length'] == '9'


def test_plain_file_streamed_for_head(client):
    response = client.head('/test/maps/foolish/arena.bsp')
    assert response.status_code == 200
    assert response.headers['content-length'] == '9'


def test_on_the_fly_bz2_is_valid(client):
    response = client.get('/test/maps/foolish/arena.bsp.bz2')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/x-bzip2'
    assert bz2.decompress(response.content) == b'ARENA-BSP'


def test_on_disk_bz2_served_exactly(client):
    expected = bz2.compress(b'DE-DUST-ON-DISK-BZ2')
    response = client.get('/test/maps/de_test/de_dust.bsp.bz2')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/x-bzip2'
    assert response.content == expected


def test_large_file_not_compressed(client):
    response = client.get('/test/maps/de_test/huge.bsp.bz2')
    assert response.status_code == 404


def test_large_file_plaintext_never_leaks_as_bz2(client):
    response = client.get('/test/maps/de_test/huge.bsp.bz2')
    assert b'XXXX' not in response.content


def test_large_file_plain_served(client):
    response = client.get('/test/maps/de_test/huge.bsp')
    assert response.status_code == 200
    assert len(response.content) == 70 * 1024


def test_missing_bz2_of_missing_file_404(client):
    response = client.get('/test/maps/foolish/ghost.bsp.bz2')
    assert response.status_code == 404


def test_bz2_head_no_body(client):
    response = client.head('/test/maps/foolish/arena.bsp.bz2')
    assert response.content == b''


def test_wav_served(client):
    response = client.get('/test/sound/vo/hello.wav')
    assert response.status_code == 200
    assert response.content == b'HELLO-WAV'


def test_nav_served(client):
    response = client.get('/test/maps/foolish/arena.nav')
    assert response.status_code == 200
    assert response.content == b'ARENA-NAV'


def test_content_length_matches_body(client):
    response = client.get('/test/maps/foolish/arena.bsp')
    assert int(response.headers['content-length']) == len(response.content)