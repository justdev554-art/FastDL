import os
import re
from typing import Iterable, Mapping

import anyio
from srctools.keyvalues import Keyvalues, NoKeyError
from srctools.tokenizer import TokenSyntaxError

from common import InternalError


PATTERN = re.compile(r'^(?:\|([A-Za-z0-9_]+)\|)?(.+)')


def extract_searchpaths(path_base: str, path_mapping: Mapping[str, str]):
    gameinfo_path = os.path.join(
        path_base, path_mapping['gameinfo_path'], 'gameinfo.txt')

    try:
        with open(gameinfo_path, encoding='utf-8') as f:
            kv = Keyvalues.parse(f, allow_escapes=False)
    except (OSError, TokenSyntaxError) as e:
        raise InternalError from e

    try:
        searchpaths = kv.find_key('GameInfo').find_key(
            'FileSystem').find_children('SearchPaths')
    except NoKeyError as e:
        raise InternalError from e

    def generate():
        processed = set()

        for item in searchpaths:
            categories = item.name.split('+')
            if not 'mod' in categories:
                continue

            if 'vpk' in categories or item.value.endswith('.vpk'):
                continue

            match = PATTERN.match(item.value)
            if not match:
                continue

            directory = match.group(1)
            path = match.group(2)

            if directory is None:
                directory = ''
            elif directory in path_mapping:
                directory = path_mapping[directory]
            else:
                continue

            path_absolute = os.path.normpath(
                os.path.join(path_base, directory, path))
            print(path_absolute)
            if path_absolute in processed:
                continue
            processed.add(path_absolute)
            yield path_absolute

    return tuple(generate())


async def resolve_searchpaths(searchpaths: Iterable[str]):
    for searchpath in searchpaths:
        searchpath = anyio.Path(searchpath)

        if searchpath.name == '*':
            if await searchpath.is_dir():
                async for path in searchpath.parent.iterdir():
                    if await path.is_dir():
                        yield await path.resolve()
        else:
            if await searchpath.is_dir():
                yield await searchpath.resolve()
