from fastdl.file import DirEntry
from fastdl.routes import Suffix, render_directory_listing

PREDICATE = Suffix('.vmt')

PAYLOAD = 'a"><script>alert(1)</script>'


def test_no_raw_payload_in_listing_html():
    html = render_directory_listing(
        '/test', '/maps', PAYLOAD, [DirEntry('x.vmt', False, 3)], PREDICATE
    )
    assert '<script>alert(1)</script>' not in html
    assert 'a">' not in html


def test_payload_percent_quoted_in_hrefs():
    html = render_directory_listing(
        '/test', '/maps', PAYLOAD, [DirEntry('x.vmt', False, 3)], PREDICATE
    )
    assert 'a%22%3E%3Cscript%3Ealert%281%29' in html


def test_title_html_escaped():
    html = render_directory_listing(
        '/test', '/maps', PAYLOAD, [DirEntry('x.vmt', False, 3)], PREDICATE
    )
    assert '&quot;&gt;&lt;script&gt;' in html
    assert '<script>alert' not in html


def test_normal_file_link_unchanged():
    html = render_directory_listing(
        '/test', '/maps', '', [DirEntry('arena.bsp', False, 123)], Suffix('.bsp')
    )
    assert 'href="/test/maps/arena.bsp"' in html


def test_space_directory_is_percent_encoded():
    html = render_directory_listing(
        '/test', '/maps', 'space dir', [DirEntry('x.vmt', False, 4)], PREDICATE
    )
    assert 'href="/test/maps/space%20dir/x.vmt"' in html


def test_percent_in_filename_is_encoded():
    html = render_directory_listing(
        '/test', '/maps', 'space dir', [DirEntry('100%odd.vmt', False, 4)], PREDICATE
    )
    assert 'href="/test/maps/space%20dir/100%25odd.vmt"' in html


def test_parent_link_is_encoded():
    html = render_directory_listing(
        '/test', '/maps', 'space dir', [DirEntry('x.vmt', False, 4)], PREDICATE
    )
    assert 'href="/test/maps/"' in html


def test_directories_precede_files():
    html = render_directory_listing(
        '/test', '/maps', '',
        [DirEntry('a.bsp', False, 1), DirEntry('zdir', True, 0)], Suffix('.bsp')
    )
    assert html.index('/zdir/') < html.index('/a.bsp')