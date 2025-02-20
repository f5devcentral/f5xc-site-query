import importlib.util
import pkgutil
import types
from types import ModuleType
from typing import Optional


def load_package_modules(package: str = None, recursive: bool = True, exclude: str = '') -> Optional[dict]:
    """ Import all submodules of a module, recursively, including subpackages

    :param package: package
    :param recursive: bool
    :type exclude: list
    :rtype: dict[str, types.ModuleType]
    """

    if isinstance(package, str):
        try:
            package = importlib.import_module(package)
        except ModuleNotFoundError as mnfe:
            print('Loading module failed with error:', mnfe)
            return None

    handler = dict()

    for loader, name, is_pkg in pkgutil.walk_packages(package.__path__):
        if not name.startswith('__') and name not in exclude:
            full_name = package.__name__ + '.' + name
            handler[name] = importlib.import_module(full_name)
            if recursive and is_pkg:
                handler.update(load_package_modules(full_name))

    return handler


def load_module(package: str = None, module: str = None) -> ModuleType | None:
    """ Import a module

    :param package: str
    :param module: str
    :rtype: types.ModuleType
    """

    if isinstance(package, str):
        try:
            package = importlib.import_module('{}.{}'.format(package, module))
        except ModuleNotFoundError as mnfe:
            print(f'Loading module {module} failed with error: {mnfe}')
            return None

        return package