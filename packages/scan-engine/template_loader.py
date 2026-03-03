"""Loads ScanRule / MTFScanRule objects from JSON template files."""
import json
import pathlib

from packages.scan_engine.scanner import ScanRule

TEMPLATES_DIR = pathlib.Path(__file__).parent / "templates"


def load_template(template_id: str) -> ScanRule:
    """
    Load a ScanRule from a JSON template file by ID.
    Raises FileNotFoundError if not found, ValueError if the file is an MTF template
    (use load_mtf_template() for those).
    """
    path = TEMPLATES_DIR / f"{template_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {template_id}")
    data = json.loads(path.read_text())
    if data.get("type") == "mtf":
        raise ValueError(f"Template {template_id} is an MTF template; use load_mtf_template()")
    return ScanRule(**data)


def load_mtf_template(template_id: str):
    """Load an MTFScanRule from a JSON template file."""
    from packages.scan_engine.mtf_scanner import MTFScanRule
    path = TEMPLATES_DIR / f"{template_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"MTF template not found: {template_id}")
    data = json.loads(path.read_text())
    if data.get("type") != "mtf":
        raise ValueError(f"Template {template_id} is not an MTF template")
    return MTFScanRule(**data)


def list_templates() -> list[dict]:
    """
    List all available scan templates (standard and MTF) with summary metadata.
    MTF templates carry type='mtf' and timeframes=[...]; standard carry type='standard'.
    """
    templates = []
    for f in sorted(TEMPLATES_DIR.glob("*.json")):
        data = json.loads(f.read_text())
        tpl_type = data.get("type", "standard")
        if tpl_type == "mtf":
            templates.append({
                "id": data["id"],
                "name": data["name"],
                "description": data["description"],
                "market": data["market"],
                "assetClass": data.get("asset_class", data.get("assetClass", "")),
                "timeframe": "MTF",
                "type": "mtf",
                "timeframes": [b["timeframe"] for b in data.get("timeframe_conditions", [])],
            })
        else:
            templates.append({
                "id": data["id"],
                "name": data["name"],
                "description": data["description"],
                "market": data["market"],
                "assetClass": data.get("asset_class", data.get("assetClass", "")),
                "timeframe": data.get("timeframe", "1day"),
                "type": "standard",
            })
    return templates
