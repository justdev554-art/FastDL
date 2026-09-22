import pytest


def test_forward_slash_traversal_rejected(client):
    # httpx normalizes raw '../' client-side before the server sees it,
    # so this arrives as '/secret.bsp' and 404s without a redirect hop.
    response = client.get('/test/maps/../../secret.bsp')
    assert response.status_code == 404
    assert 'TOP-SECRET' not in response.text


def test_backslash_traversal_redirects(client):
    response = client.get('/test/maps/..%5C..%5C..%5C..%5Csecret.bsp')
    assert response.status_code == 307
    assert response.headers['location'].endswith('/secret.bsp')


def test_encoded_forward_slash_traversal_redirects(client):
    response = client.get('/test/maps/..%2F..%2F..%2F..%2Fsecret.bsp')
    assert response.status_code == 307
    assert response.headers['location'].endswith('/secret.bsp')


def test_traversal_target_not_served(client):
    response = client.get('/secret.bsp')
    assert response.status_code == 404
    assert 'TOP-SECRET' not in response.text


@pytest.mark.parametrize('url', [
    '/test/maps/../../secret.bsp',
    '/test/maps/..%5C..%5C..%5C..%5Csecret.bsp',
    '/test/maps/..%2F..%2F..%2F..%2Fsecret.bsp',
])
def test_secret_never_leaks(client, url):
    response = client.get(url)
    assert 'TOP-SECRET' not in response.text


def test_allowed_file_still_served(client):
    response = client.get('/test/maps/foolish/arena.bsp')
    assert response.status_code == 200
    assert response.content == b'ARENA-BSP'


def test_allowed_head_still_served(client):
    response = client.head('/test/maps/foolish/arena.bsp')
    assert response.status_code == 200
    assert 'content-length' in response.headers


def test_disallowed_extension_rejected(client):
    response = client.get('/test/maps/foolish/arena.txt')
    assert response.status_code == 422


def test_missing_file_404(client):
    response = client.get('/test/maps/foolish/nope.bsp')
    assert response.status_code == 404