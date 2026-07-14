"""
HAYAT v2.0 — Legal Knowledge Graph Service
Layer 4: Connect everything. Cases, judges, statutes, principles, topics.
"""

from typing import Dict, Any, List, Optional
from uuid import uuid4

from app.core.config import settings
from app.core.logging import get_logger
from app.db.neo4j import get_neo4j_session, Neo4jQueryBuilder
from app.models.legal import Case, Statute, Section

logger = get_logger("hayat.knowledge_graph")


class KnowledgeGraphService:
    """
    Neo4j-backed legal knowledge graph.
    Builds citation networks, precedent chains, and legal principle graphs.
    """

    def __init__(self):
        self.query_builder = Neo4jQueryBuilder()

    async def create_case_node(self, case: Case) -> str:
        """Create or update a Case node in the graph."""
        async with await get_neo4j_session() as session:
            result = await session.run(
                self.query_builder.create_case({
                    "id": case.id,
                    "title": case.title,
                    "citation": case.citation,
                    "date": case.date.isoformat(),
                    "case_number": case.case_number,
                    "court_level": case.court_level.value,
                    "area_of_law": case.area_of_law,
                    "status": case.status.value,
                    "summary": case.summary or "",
                    "full_text": case.facts or "",
                })
            )
            record = await result.single()
            logger.info("case_node_created", case_id=case.id, citation=case.citation)
            return record["c"]["id"] if record else case.id

    async def create_statute_node(self, statute: Statute) -> str:
        """Create or update a Statute node."""
        async with await get_neo4j_session() as session:
            result = await session.run(
                self.query_builder.create_statute({
                    "id": statute.id,
                    "title": statute.title,
                    "act_number": statute.act_number,
                    "year": statute.year,
                    "assent_date": statute.assent_date.isoformat() if statute.assent_date else None,
                    "coming_into_force": statute.coming_into_force.isoformat() if statute.coming_into_force else None,
                    "preamble": statute.preamble or "",
                    "status": statute.status,
                })
            )
            record = await result.single()
            logger.info("statute_node_created", statute_id=statute.id, act_number=statute.act_number)
            return record["s"]["id"] if record else statute.id

    async def create_section_node(self, section: Section) -> str:
        """Create a Section node linked to its Statute."""
        async with await get_neo4j_session() as session:
            result = await session.run(
                self.query_builder.create_section({
                    "id": section.id,
                    "statute_id": section.statute_id,
                    "number": section.number,
                    "title": section.title or "",
                    "text": section.text[:2000],
                })
            )
            record = await result.single()
            return record["sec"]["id"] if record else section.id

    async def create_judge_node(self, judge_name: str, court: str) -> str:
        """Create a Judge node."""
        judge_id = f"judge_{judge_name.lower().replace(' ', '_')[:50]}"
        async with await get_neo4j_session() as session:
            result = await session.run(
                """
                MERGE (j:Judge {id: $id})
                SET j.name = $name,
                    j.court = $court,
                    j.created_at = datetime()
                RETURN j
                """,
                {"id": judge_id, "name": judge_name, "court": court}
            )
            return judge_id

    async def link_case_to_judge(self, case_id: str, judge_id: str) -> None:
        """Link a Case to a Judge (PRESIDED_OVER_BY)."""
        async with await get_neo4j_session() as session:
            await session.run(
                """
                MATCH (c:Case {id: $case_id}), (j:Judge {id: $judge_id})
                MERGE (c)-[:PRESIDED_OVER_BY]->(j)
                """,
                {"case_id": case_id, "judge_id": judge_id}
            )

    async def link_case_to_statute(
        self, case_id: str, statute_id: str, interpretation_type: str = "interprets", paragraphs: Optional[List[str]] = None
    ) -> None:
        """Link a Case to a Statute (INTERPRETS)."""
        async with await get_neo4j_session() as session:
            await session.run(
                self.query_builder.link_case_to_statute(),
                {
                    "case_id": case_id,
                    "statute_id": statute_id,
                    "interpretation_type": interpretation_type,
                    "paragraphs": paragraphs or [],
                }
            )

    async def link_case_to_case(
        self, from_case_id: str, to_case_id: str, citation_type: str = "referred", context: str = "", paragraph: str = ""
    ) -> None:
        """Link Case to Case (CITES)."""
        async with await get_neo4j_session() as session:
            await session.run(
                self.query_builder.link_case_to_case(),
                {
                    "from_case_id": from_case_id,
                    "to_case_id": to_case_id,
                    "citation_type": citation_type,
                    "context": context,
                    "paragraph": paragraph,
                }
            )

    async def create_legal_principle(self, case_id: str, principle_text: str, principle_name: Optional[str] = None) -> str:
        """Create a Legal Principle node from a case."""
        principle_id = f"principle_{uuid4().hex[:16]}"
        async with await get_neo4j_session() as session:
            await session.run(
                """
                MERGE (p:LegalPrinciple {id: $id})
                SET p.name = $name,
                    p.text = $text,
                    p.created_at = datetime()
                WITH p
                MATCH (c:Case {id: $case_id})
                MERGE (c)-[:ESTABLISHES]->(p)
                RETURN p
                """,
                {
                    "id": principle_id,
                    "name": principle_name or principle_text[:100],
                    "text": principle_text,
                    "case_id": case_id,
                }
            )
            return principle_id

    async def get_citation_network(self, case_id: str, depth: int = 2) -> List[Dict[str, Any]]:
        """Get citation network around a case."""
        async with await get_neo4j_session() as session:
            result = await session.run(
                self.query_builder.get_citation_network(case_id, depth),
                {"case_id": case_id}
            )
            records = await result.data()
            return records

    async def get_precedent_chain(self, statute_id: str) -> List[Dict[str, Any]]:
        """Get all cases interpreting a statute."""
        async with await get_neo4j_session() as session:
            result = await session.run(
                self.query_builder.get_precedent_chain(statute_id),
                {"statute_id": statute_id}
            )
            records = await result.data()
            return records

    async def search_by_principle(self, principle: str) -> List[Dict[str, Any]]:
        """Search cases by legal principle."""
        async with await get_neo4j_session() as session:
            result = await session.run(
                self.query_builder.search_by_principle(principle),
                {"principle": principle}
            )
            records = await result.data()
            return records

    async def build_case_graph(self, case: Case) -> Dict[str, Any]:
        """Build complete graph for a case: judges, statutes, citations."""
        await self.create_case_node(case)

        # Link judges
        for judge_name in case.judges:
            judge_id = await self.create_judge_node(judge_name, case.court)
            await self.link_case_to_judge(case.id, judge_id)

        # Link statutes (from parsed citations)
        if case.statutes_cited:
            for statute_ref in case.statutes_cited.get("statutes", []):
                # In production, lookup statute by act number
                pass

        logger.info("case_graph_built", case_id=case.id, judges=len(case.judges))
        return {"case_id": case.id, "status": "graph_built"}
