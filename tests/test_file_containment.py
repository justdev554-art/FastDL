import os

import pytest

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


def test_within_accepts_root(searchpath):
    assert File._within(searchpath, searchpath)


def test_within_rejects_sibling_directory(searchpath):
    sibling = os.path.realpath(os.path.join(searchpath, os.pardir))
    assert not File._within(searchpath, sibling)


@pytest.mark.skipif(not hasattr(os, 'symlink'), reason="platform lacks symlinks")
def test_symlink_escape_blocked(tmp_path):
    if not _try_symlink(tmp_path):
        pytest.skip('symlinks not usable on this filesystem')
    outside = tmp_path / 'outside.bsp'
    outside.write_text('TOPSECRET', encoding='utf-8')
    root = tmp_path / 'root'
    root.mkdir()
    (root / 'link').symlink_to(tmp_path, target_is_directory=True)
    searchpaths = [os.path.realpath(str(root))]
    assert File._get(None, os.path.join('link', 'outside.bsp'), searchpaths) is None
    assert File._list_dir(os.path.join('link'), searchpaths) is None


@pytest.mark.skipif(not hasattr(os, 'symlink'), reason="platform lacks symlinks")
def test_symlink_inside_tree_ok(tmp_path):
    if not _try_symlink(tmp_path):
        pytest.skip('symlinks not usable on this filesystem')
    target = tmp_path / 'real'
    target.mkdir()
    (target / 'x.bsp').write_text('ok', encoding='utf-8')
    root = tmp_path / 'link'
    root.symlink_to(target, target_is_directory=True)
    searchpaths = [os.path.realpath(str(root))]
    assert File._get(None, 'x.bsp', searchpaths) is not None


def _try_symlink(tmp_path) -> bool:
    target = tmp_path / '_tgt'
    target.mkdir()
    link = tmp_path / '_lnk'
    try:
        link.symlink_to(target, target_is_directory=True)
        return True
    except OSError:
        return False