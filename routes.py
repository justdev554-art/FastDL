class WithBZ2:
    def __init__(self, func):
        self._func = func
    
    def __call__(self, *args, **kwargs):
        return self._func(*args, *map(lambda arg: arg + '.bz2', args), **kwargs)

@WithBZ2
def suffix(*extensions: str):
    def predicate(path: str):
        return any(map(path.endswith, extensions))
    return predicate


ROUTES = [
    ('/maps',      'maps',      suffix('.bsp', '.nav')),
    ('/materials', 'materials', suffix('.vmt', '.vtf')),
    ('/models',    'models',    suffix('.mdl', '.phy', '.vmt', '.vtf', '.vtx', '.vvd')),
    ('/sound',     'sound',     suffix('.mp3', '.wav')),
]
