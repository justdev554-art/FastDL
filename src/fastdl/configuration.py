import json
import os

FASTDL_CONFIG_KEY     = 'FASTDL_CONFIG'
FASTDL_CONFIG_DEFAULT = 'configuration.json'

config_path = os.environ.get(FASTDL_CONFIG_KEY, FASTDL_CONFIG_DEFAULT)

with open(config_path, encoding='UTF-8') as f:
    configuration = json.load(f)

print('Configured FastDL servers:')
for server in configuration['servers']:
    print(f'  - route: {server["route"]}')
    print(f'    base: {server["path_base"]}')
    