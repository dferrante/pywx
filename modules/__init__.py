import os
import importlib

__all__ = [os.path.splitext(f)[0] for f in os.listdir(os.path.split(__file__)[0]) if os.path.splitext(f)[1] == '.py' and os.path.split(f)[1] not in ['__init__.py',]]

for module in __all__:
    importlib.import_module(f'.{module}', package='modules')
