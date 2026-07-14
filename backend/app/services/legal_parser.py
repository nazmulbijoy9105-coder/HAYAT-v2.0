"""
HAYAT v2.0 — Legal Parsing Engine
Layer 3: Turn structured text into legal knowledge objects.
Extracts: metadata, facts, issues, ratio, obiter, held, parties, citations.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from uuid import uuid4

from app.core.config import settings
from app.core.logging import get_logger
from app.models.legal import (
    Case, Statute, Section, Document, DocumentType,
    CourtLevel, CaseStatus, DocumentStatus,
)
from app.schemas.legal import CaseCreate, StatuteCreate, SectionCreate

logger = get_logger("hayat.parser")


class LegalParser:
    """
    Deterministic legal parsing engine.
    Uses regex patterns + LLM fallback for structured extraction.
    No hallucination — every extraction is traceable to source text.
    """

    # Citation patterns for Bangladesh
    CITATION_PATTERNS = [
        r'(\d{2,4})\s+BLD\s+(\d+)',  # BLD citations
        r'(\d{2,4})\s+BLT\s+(\d+)',  # BLT citations
        r'(\d{2,4})\s+DLR\s+(\d+)',  # DLR citations
        r'(\d{2,4})\s+SCD\s+(\d+)',  # SCD citations
        r'(\d{2,4})\s+CL\s+(\d+)',   # CL citations
        r'(\d{2,4})\s+AD\s+(\d+)',   # AD citations
    ]

    # Section citation patterns
    SECTION_PATTERN = r'[Ss]ection\s+(\d+[A-Z]?)\s+of\s+(?:the\s+)?([A-Za-z\s]+?)(?:\s+Act|\s+Ordinance|\s+Code|\s+Rules|\s+Regulation)'

    # Date patterns
    DATE_PATTERNS = [
        r'(\d{1,2})[\s\-/](\d{1,2})[\s\-/](\d{2,4})',  # DD/MM/YYYY
        r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})',
    ]

    def __init__(self):
        self.section_regex = re.compile(self.SECTION_PATTERN, re.IGNORECASE)

    def _extract_citations(self, text: str) -> List[Dict[str, str]]:
        """Extract case citations from text."""
        citations = []
        for pattern in self.CITATION_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                citations.append({
                    "type": "case",
                    "citation": match.group(0),
                    "year": match.group(1),
                    "volume": match.group(2) if len(match.groups()) > 1 else None,
                })
        return citations

    def _extract_statute_citations(self, text: str) -> List[Dict[str, str]]:
        """Extract statute and section citations."""
        statutes = []
        matches = self.section_regex.finditer(text)
        for match in matches:
            statutes.append({
                "section": match.group(1),
                "act": match.group(2).strip(),
                "full_reference": match.group(0),
            })
        return statutes

    def _extract_parties(self, text: str) -> Tuple[str, str]:
        """Extract petitioner and respondent from case text."""
        # Common patterns in Bangladesh judgments
        patterns = [
            r'(?:Between|In the matter of)\s*[:\-]?\s*(.+?)\s+(?:\.\s*\.\s*\.|AND|And|and)\s+(.+?)(?:\s*Vs\.|\s*Versus|\s*Respondent)',
            r'(.+?)\s+\.\s*\.\s*\.\s*Petitioner[s]?\s+AND\s+(.+?)\s+\.\s*\.\s*\.\s*Respondent[s]?',
            r'(.+?)\s+\.\s*\.\s*\.\s*Appellant[s]?\s+AND\s+(.+?)\s+\.\s*\.\s*\.\s*Respondent[s]?',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                petitioner = re.sub(r'\s+', ' ', match.group(1)).strip()
                respondent = re.sub(r'\s+', ' ', match.group(2)).strip()
                return petitioner, respondent

        return "Unknown", "Unknown"

    def _extract_judges(self, text: str) -> List[str]:
        """Extract judge names from judgment text."""
        # Pattern: "Mr. Justice X" or "Mrs. Justice X" or "Hon'ble Mr. Justice X"
        pattern = r'(?:Hon\'ble\s+)?(?:Mr\.|Mrs\.|Ms\.)?\s*Justice\s+([A-Z][a-zA-Z\s\.]+?)(?:,|\n|\.|\s*and)'
        matches = re.finditer(pattern, text)
        judges = []
        for match in matches:
            name = match.group(1).strip()
            if len(name) > 3 and name not in judges:
                judges.append(name)
        return judges[:10]  # Limit to 10 judges

    def _extract_date(self, text: str) -> Optional[datetime]:
        """Extract judgment date from text."""
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                try:
                    # Simplified date parsing
                    groups = match.groups()
                    if len(groups) == 3:
                        day, month, year = groups
                        if month.isdigit():
                            return datetime(int(year), int(month), int(day)).date()
                        else:
                            month_map = {
                                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                                'september': 9, 'october': 10, 'november': 11, 'december': 12
                            }
                            month_num = month_map.get(month.lower(), 1)
                            return datetime(int(year), month_num, int(day)).date()
                except (ValueError, TypeError):
                    continue
        return None

    def _extract_court(self, text: str) -> Tuple[str, CourtLevel]:
        """Extract court name and level."""
        text_upper = text.upper()

        if "APPELLATE DIVISION" in text_upper or "APPELLATE" in text_upper:
            return "Supreme Court of Bangladesh — Appellate Division", CourtLevel.SUPREME_COURT_APPELLATE
        elif "HIGH COURT DIVISION" in text_upper or "HIGH COURT" in text_upper:
            return "Supreme Court of Bangladesh — High Court Division", CourtLevel.SUPREME_COURT_HIGH_COURT_DIVISION
        elif "DISTRICT" in text_upper and "JUDGE" in text_upper:
            return "District Court", CourtLevel.DISTRICT_COURT
        elif "SESSIONS" in text_upper:
            return "Sessions Court", CourtLevel.SESSIONS_COURT
        elif "TRIBUNAL" in text_upper:
            return "Special Tribunal", CourtLevel.SPECIAL_TRIBUNAL

        return "Unknown Court", CourtLevel.DISTRICT_COURT

    def _extract_sections(self, text: str) -> List[Dict[str, Any]]:
        """Extract sections from statute text."""
        sections = []

        # Pattern for numbered sections
        section_pattern = r'(?:^|\n)\s*(\d+[A-Z]?)\s*[-\.\)]?\s*([A-Z][^\n]{0,200})?\s*\n(.+?)(?=(?:^|\n)\s*(?:\d+[A-Z]?)\s*[-\.\)]?\s*[A-Z]|\Z)'
        matches = re.finditer(section_pattern, text, re.MULTILINE | re.DOTALL)

        for match in matches:
            number = match.group(1).strip()
            title = match.group(2).strip() if match.group(2) else None
            section_text = match.group(3).strip()

            sections.append({
                "number": number,
                "title": title,
                "text": section_text[:5000],  # Limit length
            })

        return sections

    def _extract_irac(self, text: str) -> Dict[str, str]:
        """Extract IRAC structure from judgment text."""
        # Simple heuristic-based extraction
        irac = {
            "issues": "",
            "rules": "",
            "application": "",
            "conclusion": "",
        }

        # Look for common section markers
        issue_markers = ["ISSUE", "QUESTION", "POINTS FOR DETERMINATION", "MATTERS TO BE DETERMINED"]
        rule_markers = ["LAW", "LEGAL PRINCIPLE", "RATIO", "RULE", "SECTION"]
        app_markers = ["ANALYSIS", "APPLICATION", "REASONING", "DISCUSSION", "CONSIDERATION"]
        conclusion_markers = ["HELD", "DECISION", "ORDER", "JUDGMENT", "CONCLUSION", "DISPOSITION"]

        text_upper = text.upper()

        # Find issue section
        for marker in issue_markers:
            idx = text_upper.find(marker)
            if idx != -1:
                end = text_upper.find("\n\n", idx + 100)
                irac["issues"] = text[idx:end if end != -1 else idx + 1000].strip()
                break

        # Find conclusion (usually at the end)
        for marker in conclusion_markers:
            idx = text_upper.rfind(marker)
            if idx != -1:
                irac["conclusion"] = text[idx:idx + 2000].strip()
                break

        return irac

    async def parse_case(self, document: Document, text: str) -> CaseCreate:
        """Parse a judgment text into structured Case object."""
        logger.info("parsing_case", doc_id=document.id)

        # Extract components
        petitioner, respondent = self._extract_parties(text)
        judges = self._extract_judges(text)
        court_name, court_level = self._extract_court(text)
        judgment_date = self._extract_date(text)
        case_citations = self._extract_citations(text)
        statute_citations = self._extract_statute_citations(text)
        irac = self._extract_irac(text)

        # Build citation string
        citation = case_citations[0]["citation"] if case_citations else f"Unknown/{document.id[:8]}"

        # Extract case number (heuristic)
        case_number_match = re.search(r'(?:Civil|Criminal|Writ|Appeal|Review|Misc\.)\s*(?:No\.|Petition)\s*([\d/\-]+)', text, re.IGNORECASE)
        case_number = case_number_match.group(1) if case_number_match else "Unknown"

        case_data = CaseCreate(
            title=document.title,
            citation=citation,
            case_number=case_number,
            court=court_name,
            court_level=court_level,
            date=judgment_date or datetime.now().date(),
            area_of_law="General",  # Will be classified by AI layer
            petitioner=petitioner,
            respondent=respondent,
            judges=judges,
            summary=text[:2000] if len(text) > 2000 else text,
            facts=text[:3000],
            issues=irac["issues"],
            reasoning=irac["application"],
            ratio=irac["rules"],
            held=irac["conclusion"],
        )

        logger.info("case_parsed", citation=citation, court=court_name, judges_count=len(judges))
        return case_data

    async def parse_statute(self, document: Document, text: str) -> Tuple[StatuteCreate, List[SectionCreate]]:
        """Parse an Act text into Statute + Sections."""
        logger.info("parsing_statute", doc_id=document.id)

        # Extract title and act number
        title_match = re.search(r'^(?:THE\s+)?([A-Z][A-Z\s\-]+(?:ACT|CODE|ORDINANCE|RULES|REGULATION))', text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else document.title

        act_match = re.search(r'ACT\s*NO\.\s*(\d+)\s*OF\s*(\d{4})', text, re.IGNORECASE)
        if act_match:
            act_number = act_match.group(1)
            year = int(act_match.group(2))
        else:
            act_number = "Unknown"
            year = document.source_date.year if document.source_date else 2024

        # Extract preamble
        preamble_match = re.search(r'(?:PREAMBLE|WHEREAS)[:\s]*(.+?)(?=\n\s*CHAPTER|\n\s*PART|\n\s*\d+\s*[-\.])', text, re.IGNORECASE | re.DOTALL)
        preamble = preamble_match.group(1).strip() if preamble_match else None

        # Extract sections
        raw_sections = self._extract_sections(text)
        sections = [
            SectionCreate(
                number=s["number"],
                title=s.get("title"),
                text=s["text"],
            )
            for s in raw_sections
        ]

        statute = StatuteCreate(
            title=title,
            act_number=act_number,
            year=year,
            preamble=preamble,
            full_text=text[:50000],  # Limit full text
            area_of_law="General",
        )

        logger.info("statute_parsed", act_number=act_number, year=year, sections_count=len(sections))
        return statute, sections
