"""Root conftest.py — registers hyphenated package directories as importable Python modules.

The Nx monorepo uses kebab-case directory names (e.g. packages/data-adapters) but
Python requires valid identifiers for import paths. This file registers aliases so that
  from packages.data_adapters.xxx import Xxx
resolves to the files in packages/data-adapters/.
"""
import sys
import importlib
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).parent

# Map Python module name -> actual directory name (kebab-case)
_PACKAGE_ALIASES = {
    "packages.data_adapters": _ROOT / "packages" / "data-adapters",
    "packages.indicator_engine": _ROOT / "packages" / "indicator-engine",
    "packages.scan_engine": _ROOT / "packages" / "scan-engine",
    "packages.backtest_engine": _ROOT / "packages" / "backtest-engine",
    "packages.shared_types": _ROOT / "packages" / "shared-types",
    "packages.api_client": _ROOT / "packages" / "api-client",
}


def _register_alias(module_name: str, directory: Path) -> None:
    """Register a directory as an importable Python package under the given name."""
    if module_name in sys.modules:
        return
    if not directory.exists():
        return
    init_file = directory / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        module_name,
        init_file if init_file.exists() else None,
        submodule_search_locations=[str(directory)],
    )
    if spec is None:
        return
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    if spec.loader and init_file.exists():
        spec.loader.exec_module(module)


# Register all top-level package aliases at collection time
for _mod_name, _dir in _PACKAGE_ALIASES.items():
    _register_alias(_mod_name, _dir)
