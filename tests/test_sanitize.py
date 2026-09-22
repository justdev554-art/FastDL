from fastdl.middleware import PathSanitizeMiddleware


def test_backslash_traversal_sanitized():
    path = PathSanitizeMiddleware.sanitize(r'/test/maps/..\..\..\secret.bsp')
    assert path == '/secret.bsp'


def test_backslash_traversal_redirect_condition():
    original = r'/test/maps/..\..\..\secret.bsp'
    assert PathSanitizeMiddleware.sanitize(original) != original


def test_forward_traversal_sanitized():
    assert PathSanitizeMiddleware.sanitize('/a/../../b') == '/b'


def test_dot_segments_removed():
    assert PathSanitizeMiddleware.sanitize('/a/./b') == '/a/b'


def test_excess_traversal_capped_at_root():
    assert PathSanitizeMiddleware.sanitize('/../../secret') == '/secret'


def test_normal_path_unchanged():
    path = '/test/maps/foolish/arena.bsp'
    assert PathSanitizeMiddleware.sanitize(path) == path


def test_trailing_slash_preserved():
    assert PathSanitizeMiddleware.sanitize('/maps/foolish/') == '/maps/foolish/'


def test_root_unchanged():
    assert PathSanitizeMiddleware.sanitize('/') == '/'