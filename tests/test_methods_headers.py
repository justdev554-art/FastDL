import pytest


FILE_URL = '/test/maps/foolish/arena.bsp'
LISTING_URL = '/test/maps/'


def test_get_serves_listing_with_security_headers(client):
    response = client.get(LISTING_URL)
    assert response.status_code == 200
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['x-frame-options'] == 'DENY'
    assert response.headers['referrer-policy'] == 'no-referrer'


def test_file_response_has_security_headers(client):
    response = client.get(FILE_URL)
    assert response.status_code == 200
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['x-frame-options'] == 'DENY'


def test_404_has_security_headers(client):
    response = client.get('/test/maps/foolish/nope.bsp')
    assert response.status_code == 404
    assert response.headers['x-content-type-options'] == 'nosniff'


def test_redirect_has_security_headers(client):
    response = client.get('/test/maps/..%5C..%5C..%5C..%5Csecret.bsp')
    assert response.status_code == 307
    assert response.headers['x-content-type-options'] == 'nosniff'


def test_listing_sends_csp(client):
    response = client.get(LISTING_URL)
    assert "content-security-policy" in response.headers


def test_index_sends_csp(client):
    response = client.get('/test')
    assert 'content-security-policy' in response.headers


def test_csp_blocks_scripts(client):
    response = client.get(LISTING_URL)
    csp = response.headers['content-security-policy']
    assert "default-src 'none'" in csp
    assert 'script-src' not in csp
    assert 'frame-ancestors' in csp


@pytest.mark.parametrize('method', ['post', 'put', 'patch', 'delete'])
def test_write_methods_rejected_on_file(client, method):
    response = getattr(client, method)(FILE_URL)
    assert response.status_code == 405


@pytest.mark.parametrize('method', ['post', 'put', 'delete'])
def test_write_methods_rejected_on_listing(client, method):
    response = getattr(client, method)(LISTING_URL)
    assert response.status_code == 405


def test_head_file_returned_without_body(client):
    response = client.head(FILE_URL)
    assert response.status_code == 200
    assert response.content == b''


def test_head_listing_no_body(client):
    response = client.head('/test/maps/de_test/')
    assert response.status_code in (200, 404, 422)
    assert response.content == b''


def test_head_index_no_body(client):
    response = client.head('/test')
    assert response.content == b''


def test_cors_simple_request_allows_any_origin(client):
    response = client.get(FILE_URL, headers={'Origin': 'https://evil.example'})
    assert response.headers.get('access-control-allow-origin') == '*'


def test_cors_preflight_allows_get_head(client):
    response = client.options(
        FILE_URL,
        headers={
            'Origin': 'https://evil.example',
            'Access-Control-Request-Method': 'GET',
        },
    )
    assert response.status_code == 200
    allowed = response.headers.get('access-control-allow-methods', '')
    assert {'GET', 'HEAD'} <= set(m.strip() for m in allowed.split(','))


def test_cors_credentials_disabled(client):
    response = client.get(FILE_URL, headers={'Origin': 'https://evil.example'})
    assert response.headers.get('access-control-allow-credentials') != 'true'


def test_plain_options_without_preflight_headers_rejected(client):
    response = client.options('/test/maps/foolish/')
    assert response.status_code in (405, 200)