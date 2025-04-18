import os
import re
from typing import Mapping, Generator

from srctools.keyvalues import Keyvalues, NoKeyError
from srctools.tokenizer import TokenSyntaxError

from .common import InternalError

PATTERN = re.compile(r'^(?:\|([A-Za-z0-9_]+)\|)?(.+)')


def extract_searchpaths(path_base: str, path_mapping: Mapping[str, str]) -> Generator[str]:
    """
    Parse the 'gameinfo.txt' file located at the path given by 'path_mapping'
    and yield absolute paths for each relevant search path that meets the criteria.
    """
    try:
        gameinfo_path = os.path.join(
            path_base, path_mapping['gameinfo_path'], 'gameinfo.txt'
        )
    except KeyError as e:
        raise InternalError("Missing 'gameinfo_path' in path mappings.") from e

    try:
        with open(gameinfo_path, encoding='utf-8') as file_handle:
            keyvalues = Keyvalues.parse(file_handle, allow_escapes=False)
    except (OSError, TokenSyntaxError) as e:
        raise InternalError("Failed to read or parse 'gameinfo.txt'.") from e

    try:
        searchpaths = (
            keyvalues
            .find_key('GameInfo')
            .find_key('FileSystem')
            .find_children('SearchPaths')
        )
    except NoKeyError as e:
        raise InternalError("Missing SearchPaths in 'gameinfo.txt' structure.") from e

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

        directory_key = match.group(1)
        partial_path = match.group(2)

        if directory_key is None:
            directory = ''
        elif directory_key in path_mapping:
            directory = path_mapping[directory_key]
        else:
            # Skip if the directory key is unrecognized
            continue

        path_absolute = os.path.normpath(
            os.path.join(path_base, directory, partial_path)
        )
        if path_absolute in processed:
            continue
        processed.add(path_absolute)

        yield path_absolute
