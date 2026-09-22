import pytest

SECRET = 'TOP-SECRET'

TRAVERSAL_URLS = [
    '/test/maps/../../secret.bsp',
    '/test/maps/../..\\..\\..\\..\\secret.bsp',
    '/test/maps/..%2F..%2F..%2F..%2Fsecret.bsp',
    '/test/maps/%2e%2e/%2e%2e/%2e%2e/%2e%2e/secret.bsp',
    '/test/maps/%2E%2E/%2E%2E/%2E%2E/%2E%2E/secret.bsp',
    '/test/maps/..%5C..%5C..%5C..%5Csecret.bsp',
    '/test/maps/%2e%2e%5C%2e%2e%5C%2e%2e%5C%2e%2e%5Csecret.bsp',
    '/test/maps/.%2e/.%2e/.%2e/.%2e/secret.bsp',
    '/test/maps/..%252e%252e%252f%252e%252e%252fsecret.bsp',
    '/test/maps/....//secret.bsp',
    '/test/maps/..%5C..%5C..%5C..%5C..%5Csecret.bsp',
    '/test/maps/..%2f..%5C..%2f..%5Csecret.bsp',
    '/test/../test/maps/foolish/../../secret.bsp',
]


@pytest.mark.parametrize('url', TRAVERSAL_URLS)
def test_traversal_never_returns_secret(client, url):
    response = client.get(url)
    assert SECRET not in response.text
    assert response.status_code != 200


@pytest.mark.parametrize('url', TRAVERSAL_URLS)
def test_traversal_direct_target_404(client, url):
    response = client.get('/secret.bsp')
    assert response.status_code == 404
    assert SECRET not in response.text


def test_encoded_backslash_redirects_and_follows_cleanly(client):
    response = client.get('/test/maps/..%5C..%5C..%5C..%5Csecret.bsp')
    assert response.status_code == 307
    assert response.headers['location'].endswith('/secret.bsp')
    followed = client.get('/secret.bsp')
    assert followed.status_code == 404
    assert SECRET not in followed.text


def test_encoded_slashes_redirect_and_follow_cleanly(client):
    response = client.get('/test/maps/%2e%2e/%2e%2e/secret.bsp')
    assert response.status_code == 307
    assert response.headers['location'].endswith('/secret.bsp')


def test_dot_like_segment_is_not_traversal(client):
    response = client.get('/test/maps/.../anything.vmt')
    assert response.status_code in (404, 422)
    assert SECRET not in response.text


def test_dot_segment_normalized(client):
    response = client.get('/test/%2e/maps/%2e/foolish/')
    assert response.status_code == 307
    assert response.headers['location'].endswith('/test/maps/foolish/')


def test_double_slash_normalized(client):
    response = client.get('/test//maps/foolish/')
    assert response.status_code == 307
    assert response.headers['location'].endswith('/test/maps/foolish/')


def test_trailing_dot_segment_redirects(client):
    response = client.get('/test/maps/%2e')
    assert response.status_code == 307
    assert response.headers['location'].endswith('/test/maps')


def test_root_traversal_capped(client):
    response = client.get('/test/%2e%2e')
    assert response.status_code == 307
    assert response.headers['location'].endswith('/')


def test_bare_parent_at_root(client):
    response = client.get('/%2e%2e')
    assert response.status_code == 307
    assert response.headers['location'].endswith('/')


def test_maps_parent_segment_lands_on_index_not_secret(client):
    response = client.get('/test/maps/%2e%2e')
    assert response.status_code == 307
    assert response.headers['location'].endswith('/test')
    followed = client.get('/test')
    assert followed.status_code == 200
    assert SECRET not in followed.text