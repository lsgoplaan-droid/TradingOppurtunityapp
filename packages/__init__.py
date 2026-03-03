"""
Register kebab-case sub-package directories as importable snake_case module aliases.

This runs automatically whenever `import packages` is executed — including in uvicorn
worker subprocesses — so no separate conftest.py or startup script is needed.
"""
import sys
import pathlib
import importlib.util

_packages_dir = pathlib.Path(__file__).parent

for _pkg_dir in sorted(_packages_dir.iterdir()):
    if not _pkg_dir.is_dir():
        continue
    if not (_pkg_dir / "__init__.py").exists():
        continue
    if "-" not in _pkg_dir.name:
        continue  # already a valid Python identifier, no alias needed

    _canonical = _pkg_dir.name.replace("-", "_")
    _key = f"packages.{_canonical}"
    if _key in sys.modules:
        continue

    _spec = importlib.util.spec_from_file_location(_key, _pkg_dir / "__init__.py")
    if _spec is None:
        continue
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_key] = _mod
    try:
        _spec.loader.exec_module(_mod)
    except Exception:
        del sys.modules[_key]
