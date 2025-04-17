class Suffix:
    def __init__(self, *extensions: str):
        self._extensions = extensions + \
            tuple(map(lambda extension: extension + '.bz2', extensions))

    def __call__(self, path: str):
        return any(map(path.endswith, self._extensions))
    
    def __str__(self):
        return f'only with follwing extensions {", ".join(self._extensions)}'


ROUTES = [
    ('/maps',      'maps',      Suffix('.bsp', '.nav')),
    ('/materials', 'materials', Suffix('.vmt', '.vtf')),
    ('/models',    'models',    Suffix('.mdl', '.phy', '.vmt', '.vtf', '.vtx', '.vvd')),
    ('/sound',     'sound',     Suffix('.mp3', '.wav')),
]

print('Configured subroutes:')
for prefix, share, predicate in ROUTES:
    print(f'  - subroute: {prefix}')
    print(f'    share: {share}')
    print(f'    predicate: {predicate}')
