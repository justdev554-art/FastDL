# FastDL

An intelligent FastDL server implemented in Python, designed to automatically resolve and serve requested files with minimal configuration. This server is purpose-built for Source engine games (like Team Fortress 2, CS:GO, Left 4 Dead, etc.) to efficiently serve downloadable content to connecting players.

## Features

- **Accurate File Resolution**: Parses `gameinfo.txt` to determine the traversal order of search paths, accurately replicating the behavior of the Source Dedicated Server (SRCDS).
- **On-the-fly bz2 Compression**: Automatically compresses smaller files (<64KB) on demand when clients request `.bz2` versions, eliminating the need to store duplicate compressed copies of files.
- **Enhanced Security**: 
  - Restricts file access to a predefined set of allowed file extensions
  - Path sanitization middleware prevents path traversal attacks
  - CORS headers configured for safe cross-origin requests
- **Path Integrity Enforcement**: Prevents path manipulation through strict path filtering and normalization.
- **Dynamic Path Resolution**: Automatically handles wildcard paths in game configurations.
- **Directory Monitoring**: Watches for changes in game directories and updates available files every 30 seconds without requiring a server restart.
- **Containerized Deployment**: Includes Docker configuration for easy deployment.

## Requirements

- Python 3.13+
- Dependencies:
  - `dacite`: For configuration parsing
  - `srctools`: For Source engine file parsing
  - `starlette`: Web framework
  - `uvicorn` (recommended): ASGI server for production deployment

## Installation

### From Source

1. Clone the repository:
   ```sh
   git clone https://github.com/cyborghosting/fastdl.git
   cd fastdl
   ```

2. Install the package with development dependencies:
   ```sh
   uv sync --dev
   ```

### Using Docker

```sh
docker build -t fastdl .
docker run -p 8000:8000 -v /path/to/configuration.json:/app/configuration.json fastdl
```

## Configuration

Configuration is done via a JSON file. By default, the server looks for configuration.json in the current directory, but you can specify a different location with the `FASTDL_CONFIG` environment variable.

### Example Configuration

```json
{
  "servers": [
    {
      "route": "/tf2",
      "path_base": "/home/gameserver/tf2-server",
      "path_mapping": {
        "gameinfo_path": "tf"
      }
    },
    {
      "route": "/csgo",
      "path_base": "/home/gameserver/csgo-server",
      "path_mapping": {
        "gameinfo_path": "csgo"
      }
    }
  ]
}
```

### Configuration Fields

- **`servers`**: Array of server configurations
  - **`route`**: URL path where this server will be accessible (e.g., http://your-domain.com/tf2/)
  - **`path_base`**: Absolute path to the game server installation directory
  - **`path_mapping`**: Key-value pairs for path resolution
    - **`gameinfo_path`**: Required - relative path to the directory containing gameinfo.txt

## Usage

### Starting the Server

To run the server using Uvicorn:

```sh
uvicorn fastdl:application --host 0.0.0.0 --port 8000
```

### Environment Variables

- `FASTDL_CONFIG`: Path to configuration file (default: configuration.json)
- `UVICORN_HOST`: Host to bind (for Docker deployment)
- `UVICORN_PORT`: Port to bind (for Docker deployment)

### Client Configuration

For Source dedicated servers, configure your `server.cfg` to use your FastDL server:

```
sv_downloadurl "http://your-domain.com/tf2"
sv_allowdownload 1
sv_allowupload 1
```

## Supported File Types

The server only serves specific file types for security reasons:

- **Maps**: `.bsp`, `.nav` (and their `.bz2` compressed variants)
- **Materials**: `.vmt`, `.vtf` (and `.bz2` variants)
- **Models**: `.mdl`, `.phy`, `.vmt`, `.vtf`, `.vtx`, `.vvd` (and `.bz2` variants)
- **Scripts**: `.txt` (and `.bz2` variants) in the `scripts/items` path
- **Shaders**: `.vcs` (and `.bz2` variants)
- **Sounds**: `.mp3`, `.wav` (and `.bz2` variants)

## Compression Features

FastDL implements two approaches to file compression:

1. **Pre-compressed files**: The server can serve `.bz2` compressed files that already exist on disk.
2. **On-the-fly compression**: When a client requests a `.bz2` file that doesn't exist, the server will:
   - Look for the uncompressed version
   - For files smaller than 64KB, compress them in memory using bz2
   - Serve the compressed data without creating a permanent file
   - This saves disk space while still providing compressed downloads

This hybrid approach optimizes both server performance and bandwidth usage without requiring manual pre-compression of all files.

## Security Considerations

- The server implements strict path sanitization to prevent path traversal attacks
- Only predetermined file extensions are served
- File resolution follows the Source engine's search path rules
- Request paths are normalized to prevent access to unauthorized files

## Development

To set up a development environment:

```sh
# Install dependencies including development tools
uv sync --dev

# Run the server with auto-reload
uvicorn fastdl:application --reload

# on windows

uv run uvicorn fastdl:application --reload
```

## License

This project is licensed under the BSD 3-Clause License - see the LICENSE file for details.

## Acknowledgments

- Based on the Source engine file system structure
- Utilizes the `srctools` library for parsing Source engine files
