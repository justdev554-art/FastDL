# FastDL

An intelligent FastDL server designed to automatically resolve and serve requested files with minimal configuration.

## Features

- **Accurate File Resolution**: Parses `gameinfo.txt` to determine the traversal order of search paths for file retrieval.
- **Enhanced Security**: Restricts file access based on explicitly allowed file extensions.
- **Path Integrity Enforcement**: Prevents path traversal and mangling through strict path filtering mechanisms.
- **Path Caching**: Caches accessed file paths to improve performance and reduce redundant lookups.

## Configuration

```jsonc
{
  "/share/route": [
    "/base/path/where/game/is/installed",
    {
      "gameinfo_path": "relative/path/where/gameinfo.txt/resides"
      // Additional configuration options can be added here
    }
  ]
}
```
