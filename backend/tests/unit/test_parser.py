import pytest
from app.services.legal_parser import LegalParser

class TestLegalParser:
    @pytest.fixture
    def parser(self):
        return LegalParser()

    def test_extract_citations_bld(self, parser):
        text = "See BLD 2015 HCD 123 and DLR 2010 SC 45"
        citations = parser._extract_citations(text)
        assert len(citations) == 2
        assert citations[0]["citation"] == "BLD 2015 HCD 123"
        assert citations[0]["year"] == "2015"

    def test_extract_statute_citations(self, parser):
        text = "Under Section 42 of the Specific Relief Act, 1877"
        statutes = parser._extract_statute_citations(text)
        assert len(statutes) == 1
        assert statutes[0]["section"] == "42"
        assert "Specific Relief" in statutes[0]["act"]

    def test_extract_parties(self, parser):
        text = "Between Petitioner . . . AND Respondent . . ."
        petitioner, respondent = parser._extract_parties(text)
        assert "Petitioner" in petitioner
        assert "Respondent" in respondent

    def test_extract_judges(self, parser):
        text = "Hon'ble Mr. Justice Abdul Malik presided. Mr. Justice Rahman concurred."
        judges = parser._extract_judges(text)
        assert len(judges) >= 1
        assert any("Malik" in j for j in judges)

    def test_detect_language_english(self, parser):
        assert parser._detect_language("This is English text") == "eng"

    def test_detect_language_bengali(self, parser):
        assert parser._detect_language("এটি বাংলা টেক্সট") == "ben"

    def test_detect_language_mixed(self, parser):
        assert parser._detect_language("This is English এবং বাংলা mixed") == "ben+eng"
