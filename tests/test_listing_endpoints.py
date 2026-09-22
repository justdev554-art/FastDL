def test_index_lists_all_subroutes(client):
    response = client.get('/test')
    assert response.status_code == 200
    for subroute in ('maps', 'materials', 'models', 'scripts/items', 'shaders', 'sound'):
        assert f'/{subroute}/' in response.text


def test_subroute_listing(client):
    response = client.get('/test/maps/')
    assert response.status_code == 200
    assert 'href="/test/maps/foolish/"' in response.text
    assert 'href="/test/maps/de_test/"' in response.text
    assert 'href="/test/maps/space%20dir/"' in response.text


def test_nested_listing_shows_files(client):
    response = client.get('/test/maps/foolish/')
    assert response.status_code == 200
    assert 'href="/test/maps/foolish/arena.bsp"' in response.text
    assert 'href="/test/maps/foolish/arena.nav"' in response.text


def test_listing_filters_disallowed_extensions(client):
    response = client.get('/test/maps/space%20dir/')
    assert response.status_code == 200
    assert 'href="/test/maps/space%20dir/usable.nav"' in response.text
    assert 'notes.txt' not in response.text
    assert 'payload.vmt' not in response.text


def test_space_dir_name_is_encoded_in_links(client):
    response = client.get('/test/maps/space%20dir/')
    assert response.status_code == 200
    assert 'href="/test/maps/space%20dir/usable.nav"' in response.text
    assert 'href="/test/maps/space dirt' not in response.text


def test_parent_link_present(client):
    response = client.get('/test/maps/foolish/')
    assert 'href="/test/maps/"' in response.text


def test_non_listing_bare_subroute(client):
    response = client.get('/test/maps')
    assert response.status_code == 200


def test_sound_listing_shows_subdirs(client):
    response = client.get('/test/sound/')
    assert response.status_code == 200
    assert 'href="/test/sound/vo/"' in response.text


def test_sound_subdir_listing_shows_files(client):
    response = client.get('/test/sound/vo/')
    assert response.status_code == 200
    assert 'href="/test/sound/vo/hello.wav"' in response.text