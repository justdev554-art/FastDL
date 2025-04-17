import asyncio
import concurrent.futures
import os
import re
from typing import Iterable, Mapping, Tuple

from srctools.keyvalues import Keyvalues, NoKeyError
from srctools.tokenizer import TokenSyntaxError

from common import InternalError


PATTERN = re.compile(r'^(?:\|([A-Za-z0-9_]+)\|)?(.+)')


def extract_searchpaths(path_base: str, path_mapping: Mapping[str, str]) -> Tuple[str]:
    try:
        gameinfo_path = os.path.join(
            path_base, path_mapping['gameinfo_path'], 'gameinfo.txt')
    except KeyError as e:
        raise InternalError from e

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
            if path_absolute in processed:
                continue
            processed.add(path_absolute)

            yield path_absolute

    return tuple(generate())


async def resolve(pool: concurrent.futures.ThreadPoolExecutor, searchpath: str) -> Tuple[str]:
    loop = asyncio.get_running_loop()

    def func():
        if os.path.basename(searchpath) == '*' and os.path.isdir(os.path.dirname(searchpath)):
            return tuple((os.path.realpath(subpath) for subpath in os.listdir(os.path.dirname(searchpath)) if os.path.isdir(subpath)))
        elif os.path.isdir(searchpath):
            return tuple((os.path.realpath(searchpath), ))
        else:
            return tuple(())

    return await loop.run_in_executor(pool, func)


async def resolve_searchpaths(searchpaths: Iterable[str]) -> Tuple[str]:
    with concurrent.futures.ThreadPoolExecutor() as pool:
        async with asyncio.TaskGroup() as group:
            tasks = tuple((group.create_task(resolve(pool, searchpath))
                          for searchpath in searchpaths))

    return tuple(path for task in tasks for path in task.result())
