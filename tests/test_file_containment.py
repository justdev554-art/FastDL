import os

from fastdl.file import File


def test_blocks_forward_slash_escape(searchpath):
    assert File._get(None, '../../../../secret.bsp', [searchpath]) is None


def test_blocks_backslash_escape(searchpath):
    assert File._get(None, r'..\..\..\..\secret.bsp', [searchpath]) is None


def test_blocks_mixed_separator_escape(searchpath):
    assert File._get(None, r'maps/..\..\..\secret.bsp', [searchpath]) is None


def test_blocks_wildcard_escape(searchpath):
    assert File._get(None, 'space dir/..\\..\\..\\..\\secret.bsp', [searchpath]) is None


def test_allows_in_tree_file(searchpath):
    result = File._get(None, 'foolish/arena.bsp', [searchpath])
    assert result is not None
    file_path, _ = result
    assert file_path == os.path.realpath(os.path.join(searchpath, 'foolish', 'arena.bsp'))


def test_missing_file_returns_none(searchpath):
    assert File._get(None, 'foolish/nope.bsp', [searchpath]) is None


def test_blocks_directory_listing_escape(searchpath):
    assert File._list_dir('../../../..', [searchpath]) is None


def test_allows_directory_listing(searchpath):
    entries = File._list_dir('foolish', [searchpath])
    assert entries is not None
    assert {entry.name for entry in entries} >= {'arena.bsp', 'arena.nav'}


def test_within_rejects_sibling(searchpath):
    sibling = os.path.realpath(os.path.join(searchpath, os.pardir, os.pardir))
    assert not File._within(searchpath, os.path.join(sibling, 'secret.bsp'))


def test_within_accepts_child(searchpath):
    child = os.path.realpath(os.path.join(searchpath, 'foolish'))
    assert File._within(searchpath, child)