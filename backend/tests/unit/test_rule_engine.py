import pytest
from app.services.rule_engine import RuleEngine, RuleCategory, RuleStatus

class TestRuleEngine:
    @pytest.fixture
    def engine(self):
        return RuleEngine()

    def test_get_rule_exists(self, engine):
        rule = engine.get_rule("sra_42_v1")
        assert rule is not None
        assert rule.title == "Mandatory Injunction"
        assert rule.statute_name == "Specific Relief Act, 1877"
        assert rule.section_number == "42"

    def test_get_rule_not_exists(self, engine):
        assert engine.get_rule("nonexistent") is None

    def test_get_rules_by_statute(self, engine):
        rules = engine.get_rules_by_statute("Specific Relief Act, 1877")
        assert len(rules) >= 1
        assert all(r.statute_name == "Specific Relief Act, 1877" for r in rules)

    def test_get_rules_by_category(self, engine):
        rules = engine.get_rules_by_category(RuleCategory.CIVIL)
        assert len(rules) >= 1

    def test_evaluate_rule_structure(self, engine):
        result = engine.evaluate_rule("sra_42_v1", {})
        assert result["rule_id"] == "sra_42_v1"
        assert "ingredients" in result
        assert "applicable_exceptions" in result
        assert "consequences_if_passed" in result
        assert "practical_tests" in result
        assert "checklist" in result

    def test_generate_checklist(self, engine):
        checklist = engine.generate_checklist("sra_42_v1")
        assert len(checklist) > 0
        assert any("title" in item.lower() for item in checklist)

    def test_to_dict_serialization(self, engine):
        rule = engine.get_rule("sra_42_v1")
        data = engine.to_dict(rule)
        assert data["id"] == "sra_42_v1"
        assert "ingredients" in data
        assert "plain_language" in data
        assert "checklist" in data
