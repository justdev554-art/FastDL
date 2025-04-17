# FastDL

An intelligent FastDL server implemented in Python, designed to automatically resolve and serve requested files with minimal configuration.

## Features

- **Accurate File Resolution**: Parses `gameinfo.txt` to determine the traversal order of search paths, accurately replicating the behavior of the Source Dedicated Server (SRCDS).
- **Enhanced Security**: Restricts file access to a predefined set of allowed file extensions.
- **Path Integrity Enforcement**: Prevents path traversal and manipulation through strict path filtering.
- **Path Caching**: Caches resolved file paths to improve performance and reduce redundant filesystem lookups.

## Usage

To start the FastDL server, use any ASGI-compatible web server such as **Uvicorn**, **Daphne**, or **Hypercorn**.

To run the server using Uvicorn:

```sh
uvicorn fastdl:app --host 0.0.0.0 --port 8000
```

## Configuration

```jsonc
{
  "servers": [
    {
      "route": "/path/where/this/server/can/be/accessed",
      "path_base": "/path/where/srcds/is/installed",
      "path_mapping": {
        "gameinfo_path": "/path/where/gameinfo.txt/file/is"
        // Additional resolution settings can be specified here
      }
    },
    {
      "route": "/csgo",
      "path_base": "/home/gameserver/csgo-srcds",
      "path_mapping": {
        "gameinfo_path": "csgo"
      }
    },
    {
      "route": "/left4dead2",
      "path_base": "/home/gameserver/left4dead2-srcds",
      "path_mapping": {
        "gameinfo_path": "l4d2"
      }
    }
  ]
}
```
