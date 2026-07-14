"""
HAYAT v2.0 — Neo4j Knowledge Graph Connection
Legal entity relationships, citation networks, and precedent chains.
"""

from typing import Optional, List, Dict, Any

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("hayat.db.neo4j")

_driver: Optional[AsyncDriver] = None


async def get_neo4j_driver() -> AsyncDriver:
    """Get or create Neo4j async driver."""
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            max_connection_lifetime=settings.neo4j_max_connection_lifetime,
            max_connection_pool_size=settings.neo4j_max_connection_pool_size,
        )
        await _driver.verify_connectivity()
        logger.info("neo4j_driver_created")
    return _driver


async def get_neo4j_session() -> AsyncSession:
    """Get a Neo4j session."""
    driver = await get_neo4j_driver()
    return driver.session()


async def init_neo4j() -> None:
    """Initialize Neo4j schema and constraints."""
    driver = await get_neo4j_driver()
    async with driver.session() as session:
        # Constraints for uniqueness
        constraints = [
            "CREATE CONSTRAINT case_id IF NOT EXISTS FOR (c:Case) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT statute_id IF NOT EXISTS FOR (s:Statute) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT section_id IF NOT EXISTS FOR (sec:Section) REQUIRE sec.id IS UNIQUE",
            "CREATE CONSTRAINT judge_id IF NOT EXISTS FOR (j:Judge) REQUIRE j.id IS UNIQUE",
            "CREATE CONSTRAINT court_id IF NOT EXISTS FOR (ct:Court) REQUIRE ct.id IS UNIQUE",
            "CREATE CONSTRAINT principle_id IF NOT EXISTS FOR (p:LegalPrinciple) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT party_id IF NOT EXISTS FOR (pt:Party) REQUIRE pt.id IS UNIQUE",
            "CREATE CONSTRAINT lawyer_id IF NOT EXISTS FOR (l:Lawyer) REQUIRE l.id IS UNIQUE",
            "CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE",
            "CREATE CONSTRAINT citation_id IF NOT EXISTS FOR (ci:Citation) REQUIRE ci.id IS UNIQUE",
        ]

        for constraint in constraints:
            try:
                await session.run(constraint)
            except Exception as e:
                logger.warning("neo4j_constraint_exists", constraint=constraint, error=str(e))

        # Indexes for performance
        indexes = [
            "CREATE INDEX case_date IF NOT EXISTS FOR (c:Case) ON (c.date)",
            "CREATE INDEX case_citation IF NOT EXISTS FOR (c:Case) ON (c.citation)",
            "CREATE INDEX statute_year IF NOT EXISTS FOR (s:Statute) ON (s.year)",
            "CREATE INDEX section_number IF NOT EXISTS FOR (sec:Section) ON (sec.number)",
        ]

        for index in indexes:
            try:
                await session.run(index)
            except Exception as e:
                logger.warning("neo4j_index_exists", index=index, error=str(e))

    logger.info("neo4j_initialized")


async def close_neo4j() -> None:
    """Close Neo4j driver."""
    global _driver
    if _driver:
        await _driver.close()
        _driver = None
        logger.info("neo4j_closed")


class Neo4jQueryBuilder:
    """
    Cypher query builder for common legal knowledge graph operations.
    """

    @staticmethod
    def create_case(case_data: Dict[str, Any]) -> str:
        return """
        MERGE (c:Case {id: $id})
        SET c.title = $title,
            c.citation = $citation,
            c.date = date($date),
            c.case_number = $case_number,
            c.court_level = $court_level,
            c.area_of_law = $area_of_law,
            c.status = $status,
            c.summary = $summary,
            c.full_text = $full_text,
            c.created_at = datetime(),
            c.updated_at = datetime()
        RETURN c
        """

    @staticmethod
    def create_statute(statute_data: Dict[str, Any]) -> str:
        return """
        MERGE (s:Statute {id: $id})
        SET s.title = $title,
            s.act_number = $act_number,
            s.year = $year,
            s.assent_date = date($assent_date),
            s.coming_into_force = date($coming_into_force),
            s.preamble = $preamble,
            s.status = $status,
            s.created_at = datetime(),
            s.updated_at = datetime()
        RETURN s
        """

    @staticmethod
    def create_section(section_data: Dict[str, Any]) -> str:
        return """
        MERGE (sec:Section {id: $id})
        SET sec.number = $number,
            sec.title = $title,
            sec.text = $text,
            sec.created_at = datetime(),
            sec.updated_at = datetime()
        WITH sec
        MATCH (s:Statute {id: $statute_id})
        MERGE (s)-[:HAS_SECTION]->(sec)
        RETURN sec
        """

    @staticmethod
    def link_case_to_statute() -> str:
        return """
        MATCH (c:Case {id: $case_id}), (s:Statute {id: $statute_id})
        MERGE (c)-[r:INTERPRETS]->(s)
        SET r.interpretation_type = $interpretation_type,
            r.paragraphs = $paragraphs,
            r.created_at = datetime()
        RETURN r
        """

    @staticmethod
    def link_case_to_case() -> str:
        return """
        MATCH (c1:Case {id: $from_case_id}), (c2:Case {id: $to_case_id})
        MERGE (c1)-[r:CITES {type: $citation_type}]->(c2)
        SET r.context = $context,
            r.paragraph = $paragraph,
            r.created_at = datetime()
        RETURN r
        """

    @staticmethod
    def get_citation_network(case_id: str, depth: int = 2) -> str:
        return f"""
        MATCH path = (c:Case {{id: $case_id}})-[:CITES*1..{depth}]-(related:Case)
        WITH c, related, path
        RETURN c.id as source_id, c.title as source_title,
               related.id as target_id, related.title as target_title,
               length(path) as distance,
               [node in nodes(path) | node.id] as path_nodes
        ORDER BY distance
        """

    @staticmethod
    def get_precedent_chain(statute_id: str) -> str:
        return """
        MATCH (s:Statute {id: $statute_id})<-[:INTERPRETS]-(c:Case)
        OPTIONAL MATCH (c)-[:CITES]->(prec:Case)
        RETURN c.id as case_id, c.title as case_title, c.date as case_date,
               collect(DISTINCT prec.id) as precedents_cited
        ORDER BY c.date DESC
        """

    @staticmethod
    def search_by_principle(principle: str) -> str:
        return """
        MATCH (p:LegalPrinciple)
        WHERE p.text CONTAINS $principle OR p.name CONTAINS $principle
        MATCH (p)<-[:ESTABLISHES]-(c:Case)
        RETURN c.id as case_id, c.title as case_title, c.citation as citation,
               p.name as principle_name, p.text as principle_text
        ORDER BY c.date DESC
        """
