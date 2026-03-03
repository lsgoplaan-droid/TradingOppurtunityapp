"""Tests for template_loader — loading and listing scan templates."""
import pytest

from packages.scan_engine.template_loader import load_template, list_templates
from packages.scan_engine.scanner import ScanRule


# ─── list_templates() tests ───────────────────────────────────────────────────

def test_list_templates_returns_at_least_8():
    """list_templates() must return at least 8 templates."""
    templates = list_templates()
    assert isinstance(templates, list)
    assert len(templates) >= 8


def test_list_templates_returns_all_8():
    """list_templates() returns exactly the 8 expected templates."""
    templates = list_templates()
    template_ids = {t["id"] for t in templates}
    expected_ids = {
        "us_eq_golden_cross",
        "us_eq_death_cross",
        "us_eq_rsi_oversold_bounce",
        "us_eq_macd_bullish_cross",
        "us_eq_breakout_volume",
        "us_eq_mean_reversion",
        "us_opt_high_iv_rank",
        "us_opt_low_iv_rank",
    }
    assert expected_ids.issubset(template_ids)


def test_list_templates_has_required_fields():
    """Each template summary must have id, name, description, market, assetClass, timeframe."""
    templates = list_templates()
    required_fields = {"id", "name", "description", "market", "assetClass", "timeframe"}
    for t in templates:
        assert required_fields.issubset(
            t.keys()
        ), f"Template {t.get('id')} is missing required fields"


# ─── load_template() tests for each of the 8 templates ───────────────────────

def test_load_us_eq_golden_cross():
    """Load us_eq_golden_cross and verify key fields."""
    rule = load_template("us_eq_golden_cross")
    assert isinstance(rule, ScanRule)
    assert rule.id == "us_eq_golden_cross"
    assert rule.market == "US"
    assert rule.asset_class == "EQUITY"
    assert rule.timeframe == "1day"
    assert rule.min_candles >= 200
    assert len(rule.conditions) >= 2
    assert rule.signal_name == "Golden Cross"
    assert rule.template_id == "us_eq_golden_cross"


def test_load_us_eq_death_cross():
    """Load us_eq_death_cross and verify key fields."""
    rule = load_template("us_eq_death_cross")
    assert isinstance(rule, ScanRule)
    assert rule.id == "us_eq_death_cross"
    assert rule.market == "US"
    assert rule.asset_class == "EQUITY"
    assert len(rule.conditions) >= 2


def test_load_us_eq_rsi_oversold_bounce():
    """Load us_eq_rsi_oversold_bounce and verify key fields."""
    rule = load_template("us_eq_rsi_oversold_bounce")
    assert isinstance(rule, ScanRule)
    assert rule.id == "us_eq_rsi_oversold_bounce"
    assert rule.market == "US"
    assert rule.asset_class == "EQUITY"
    assert len(rule.conditions) >= 1


def test_load_us_eq_macd_bullish_cross():
    """Load us_eq_macd_bullish_cross and verify key fields."""
    rule = load_template("us_eq_macd_bullish_cross")
    assert isinstance(rule, ScanRule)
    assert rule.id == "us_eq_macd_bullish_cross"
    assert rule.market == "US"
    assert rule.asset_class == "EQUITY"
    # Should have MACD-related conditions
    condition_types = [c.get("type") for c in rule.conditions]
    assert "crosses_above" in condition_types or "greater_than" in condition_types


def test_load_us_eq_breakout_volume():
    """Load us_eq_breakout_volume and verify key fields."""
    rule = load_template("us_eq_breakout_volume")
    assert isinstance(rule, ScanRule)
    assert rule.id == "us_eq_breakout_volume"
    assert rule.market == "US"
    assert rule.asset_class == "EQUITY"
    # Should have volume_surge condition
    condition_types = [c.get("type") for c in rule.conditions]
    assert "volume_surge" in condition_types


def test_load_us_eq_mean_reversion():
    """Load us_eq_mean_reversion and verify key fields."""
    rule = load_template("us_eq_mean_reversion")
    assert isinstance(rule, ScanRule)
    assert rule.id == "us_eq_mean_reversion"
    assert rule.market == "US"
    assert rule.asset_class == "EQUITY"
    assert len(rule.conditions) >= 2


def test_load_us_opt_high_iv_rank():
    """Load us_opt_high_iv_rank and verify it's an EQUITY_OPTIONS template."""
    rule = load_template("us_opt_high_iv_rank")
    assert isinstance(rule, ScanRule)
    assert rule.id == "us_opt_high_iv_rank"
    assert rule.market == "US"
    assert rule.asset_class == "EQUITY_OPTIONS"


def test_load_us_opt_low_iv_rank():
    """Load us_opt_low_iv_rank and verify it's an EQUITY_OPTIONS template."""
    rule = load_template("us_opt_low_iv_rank")
    assert isinstance(rule, ScanRule)
    assert rule.id == "us_opt_low_iv_rank"
    assert rule.market == "US"
    assert rule.asset_class == "EQUITY_OPTIONS"
    # Should have between condition for RSI
    condition_types = [c.get("type") for c in rule.conditions]
    assert "between" in condition_types


# ─── Error handling ───────────────────────────────────────────────────────────

def test_load_template_missing_raises_file_not_found():
    """load_template() raises FileNotFoundError for a non-existent template."""
    with pytest.raises(FileNotFoundError, match="Template not found"):
        load_template("this_template_does_not_exist_xyz")


def test_load_template_returns_scan_rule_instance():
    """load_template() always returns a ScanRule Pydantic model."""
    rule = load_template("us_eq_golden_cross")
    assert isinstance(rule, ScanRule)
    # ScanRule fields are accessible
    assert hasattr(rule, "id")
    assert hasattr(rule, "name")
    assert hasattr(rule, "conditions")
    assert hasattr(rule, "min_candles")


def test_load_template_conditions_are_list_of_dicts():
    """Each template's conditions field is a list of dicts."""
    templates = list_templates()
    # Skip MTF templates — they have timeframe_conditions, not conditions
    non_mtf_templates = [t for t in templates if t.get("type") != "mtf"]
    for t in non_mtf_templates:
        rule = load_template(t["id"])
        assert isinstance(rule.conditions, list)
        for cond in rule.conditions:
            assert isinstance(cond, dict)
            assert "type" in cond, f"Condition in {t['id']} missing 'type' key"
