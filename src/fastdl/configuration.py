import json
import os
from dataclasses import dataclass
from typing import List, Mapping

from dacite import from_dict

# Constants
FASTDL_CONFIG_KEY = 'FASTDL_CONFIG'
FASTDL_CONFIG_DEFAULT = 'configuration.json'

# Resolve configuration path
conf_path = os.environ.get(FASTDL_CONFIG_KEY, FASTDL_CONFIG_DEFAULT)


@dataclass(frozen=True, slots=True)
class Server:
    route: str
    path_base: str
    path_mapping: Mapping[str, str]
    # optional
    compress_max_size: int = 64 * 1024 # 64 KiB


@dataclass(frozen=True, slots=True)
class Configuration:
    servers: List[Server]
    # optional
    max_threads: int = 64


def configure() -> Configuration:
    """
    Load and parse the configuration file into a Configuration object.
    """
    if not os.path.isfile(conf_path):
        raise FileNotFoundError(f"Configuration file not found: {conf_path}")

    try:
        with open(conf_path, encoding='UTF-8') as f:
            data = json.load(f)
            return from_dict(data_class=Configuration, data=data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file: {conf_path}") from e


def display_configuration(conf: Configuration) -> None:
    """
    Display the loaded configuration in a human-readable format.
    """
    print(f"Using configuration file: {conf_path}")
    print("\nConfigured settings:")
    print(f"  - max_threads: {conf.max_threads}")
    print("\nConfigured FastDL servers:")
    for server in conf.servers:
        _display_server(server)


def _display_server(server: Server) -> None:
    """
    Display details of a single server configuration.
    """
    print(f"  - route: {server.route}")
    print(f"    path_base: {server.path_base}")
    print(f"    path_mapping:")
    for key, value in server.path_mapping.items():
        print(f"       {key}: {value}")
    print(f"    compress_max_size: {server.compress_max_size} bytes")
