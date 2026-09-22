def test_index_hides_missing_subroute(client):
    response = client.get('/test')
    assert response.status_code == 200
    assert '/models/' not in response.text
    assert 'models' not in response.text


def test_index_hides_empty_subroute(client):
    response = client.get('/test')
    assert response.status_code == 200
    assert '/shaders/' not in response.text
    assert 'shaders' not in response.text


def test_index_shows_populated_subroutes(client):
    response = client.get('/test')
    assert response.status_code == 200
    for subroute in ('maps', 'materials', 'scripts/items', 'sound'):
        assert f'/{subroute}/' in response.text


def test_empty_subdirectory_hidden_from_listing(client):
    response = client.get('/test/maps/')
    assert response.status_code == 200
    assert 'empty_dir' not in response.text
    assert 'href="/test/maps/foolish/"' in response.text


def test_non_empty_subdirectory_visible(client):
    response = client.get('/test/maps/')
    assert response.status_code == 200
    for href in ('/test/maps/foolish/', '/test/maps/de_test/', '/test/maps/space%20dir/'):
        assert f'href="{href}"' in response.text


def test_empty_subdirectory_still_navigable_directly(client):
    response = client.get('/test/maps/empty_dir/')
    assert response.status_code == 200
    assert '(empty)' in response.text


def test_empty_shaders_dir_still_navigable_directly(client):
    response = client.get('/test/shaders/')
    assert response.status_code == 200
    assert '(empty)' in response.text


def test_index_without_any_subroute_shows_placeholder():
    from fastdl.routes import render_server_index

    html = render_server_index('/test', [])
    assert '(no content)' in html