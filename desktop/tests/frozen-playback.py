"""Run playback/progress/selection regressions against the built engine's PYZ.

Requires the same Python version as the engine and PyInstaller. No credentials
or installed user data are used. All core imports must come from the archive.
"""
import importlib.abc
import importlib.util
from pathlib import Path
import sys
import unittest

from PyInstaller.archive.readers import CArchiveReader

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / 'core'
archive = CArchiveReader(str(ROOT / 'desktop/engine/nyxor-engine/nyxor-engine.exe'))
pyz = archive.open_embedded_archive('PYZ.pyz')
sources = {}
for file in CORE.rglob('*.py'):
    parts = list(file.relative_to(CORE).with_suffix('').parts)
    if parts[-1] == '__init__':
        parts.pop()
    sources['.'.join(parts)] = file


class FrozenCore(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    loaded = set()

    def find_spec(self, fullname, path=None, target=None):
        if fullname not in sources:
            return None
        if fullname not in pyz.toc:
            raise ImportError(f'Core module missing from frozen engine: {fullname}')
        return importlib.util.spec_from_loader(fullname, self, is_package=pyz.toc[fullname][0] == 1)

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__file__ = str(sources[module.__name__])
        if module.__spec__.submodule_search_locations is not None:
            module.__path__ = [str(sources[module.__name__].parent)]
        self.loaded.add(module.__name__)
        exec(pyz.extract(module.__name__), module.__dict__)


loader = FrozenCore()
sys.meta_path.insert(0, loader)
sys.path.insert(0, str(ROOT / 'tests'))
suite = unittest.defaultTestLoader.loadTestsFromNames([
    'test_playback', 'test_drop_progress', 'test_drop_selection',
])
result = unittest.TextTestRunner(verbosity=2).run(suite)
assert {'nyxor_player', 'nyxor.drop_progress', 'nyxor.drop_selection', 'nyxor_core'} <= loader.loaded
print(f'Tested {len(loader.loaded)} core modules loaded from the frozen engine; no source fallback.')
sys.exit(0 if result.wasSuccessful() else 1)
