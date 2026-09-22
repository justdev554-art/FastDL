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


def test_backslash_only_path_clean():
    assert PathSanitizeMiddleware.sanitize(r'\test\maps\foolish') == '/test/maps/foolish'


def test_double_encoded_dots_are_not_decoded():
    path = '/test/maps/%252e%252e%252fsecret.bsp'
    assert PathSanitizeMiddleware.sanitize(path) == path


def test_dot_dot_dot_is_normal_segment():
    assert PathSanitizeMiddleware.sanitize('/a/.../b') == '/a/.../b'


def test_empty_path_yields_root():
    assert PathSanitizeMiddleware.sanitize('') == '/'


def test_repeated_traversal_fully_removed():
    assert PathSanitizeMiddleware.sanitize('/a/b/../../../../c') == '/c'


def test_interleaved_separators():
    assert PathSanitizeMiddleware.sanitize(r'\a\..\c') == '/c'


def test_backslash_dotdot_not_misread_as_normal_segment():
    assert PathSanitizeMiddleware.sanitize('/a/..5') == '/a/..5'


def test_dots_inside_segment_not_treated_as_parent():
    assert PathSanitizeMiddleware.sanitize('/a/b../..c') == '/a/b../..c'


def test_multiple_consecutive_slashes_collapsed():
    assert PathSanitizeMiddleware.sanitize('/a//b///c') == '/a/b/c'


def test_parent_like_tokens_in_query_not_in_path():
    assert PathSanitizeMiddleware.sanitize('/a/b') == '/a/b'