"""
HAYAT v2.0 — Analytics Engine
Layer 10: Judge analytics, section analytics, case trends, citation heatmaps.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from collections import Counter, defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.core.config import settings
from app.core.logging import get_logger
from app.models.legal import Case, Statute, Section, AuditLog
from app.db.neo4j import get_neo4j_session

logger = get_logger("hayat.analytics")


class AnalyticsEngine:
    """
    Legal analytics for strategic litigation and policy research.
    """

    async def judge_analytics(self, judge_name: str, db: AsyncSession) -> Dict[str, Any]:
        """Comprehensive analytics for a specific judge."""
        # Total cases
        total_result = await db.execute(
            select(func.count(Case.id)).where(Case.judges.contains([judge_name]))
        )
        total_cases = total_result.scalar()

        # Cases by area of law
        area_result = await db.execute(
            select(Case.area_of_law, func.count(Case.id))
            .where(Case.judges.contains([judge_name]))
            .group_by(Case.area_of_law)
        )
        cases_by_area = {row[0]: row[1] for row in area_result.all()}

        # Cases by year
        year_result = await db.execute(
            select(func.extract('year', Case.date), func.count(Case.id))
            .where(Case.judges.contains([judge_name]))
            .group_by(func.extract('year', Case.date))
            .order_by(func.extract('year', Case.date))
        )
        cases_by_year = {str(int(row[0])): row[1] for row in year_result.all()}

        # Average case length (hearing to judgment)
        avg_length_result = await db.execute(
            select(func.avg(
                func.extract('epoch', Case.date_judgment - Case.date_hearing) / 86400
            )).where(
                and_(
                    Case.judges.contains([judge_name]),
                    Case.date_hearing.isnot(None),
                    Case.date_judgment.isnot(None),
                )
            )
        )
        avg_length = avg_length_result.scalar()

        # Most cited by this judge
        # Would query Neo4j for citation network

        return {
            "judge_name": judge_name,
            "total_cases": total_cases,
            "cases_by_area": cases_by_area,
            "cases_by_year": cases_by_year,
            "average_case_length_days": round(avg_length, 1) if avg_length else None,
            "most_active_areas": sorted(cases_by_area.items(), key=lambda x: x[1], reverse=True)[:5],
            "trend": "increasing" if cases_by_year.get("2024", 0) > cases_by_year.get("2023", 0) else "stable",
        }

    async def section_analytics(self, statute_id: str, db: AsyncSession) -> Dict[str, Any]:
        """Analytics for a specific statute section."""
        # Cases interpreting this section
        from app.models.legal import case_statutes
        cases_result = await db.execute(
            select(func.count(case_statutes.c.case_id))
            .where(case_statutes.c.statute_id == statute_id)
        )
        interpreting_cases = cases_result.scalar()

        # Interpretation types distribution
        interp_result = await db.execute(
            select(case_statutes.c.interpretation_type, func.count(case_statutes.c.case_id))
            .where(case_statutes.c.statute_id == statute_id)
            .group_by(case_statutes.c.interpretation_type)
        )
        interpretation_types = {row[0] or "unknown": row[1] for row in interp_result.all()}

        return {
            "statute_id": statute_id,
            "interpreting_cases": interpreting_cases,
            "interpretation_types": interpretation_types,
            "most_common_interpretation": max(interpretation_types, key=interpretation_types.get) if interpretation_types else None,
        }

    async def case_trends(
        self,
        db: AsyncSession,
        area_of_law: Optional[str] = None,
        court_level: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        granularity: str = "year",
    ) -> Dict[str, Any]:
        """Case filing trends over time."""
        query = select(Case)

        if area_of_law:
            query = query.where(Case.area_of_law == area_of_law)
        if court_level:
            query = query.where(Case.court_level == court_level)
        if start_date:
            query = query.where(Case.date >= start_date)
        if end_date:
            query = query.where(Case.date <= end_date)

        # Group by time period
        if granularity == "year":
            period_expr = func.extract('year', Case.date)
        elif granularity == "quarter":
            period_expr = func.concat(
                func.extract('year', Case.date),
                '-Q',
                func.extract('quarter', Case.date)
            )
        else:
            period_expr = func.to_char(Case.date, 'YYYY-MM')

        trend_result = await db.execute(
            select(period_expr, func.count(Case.id))
            .group_by(period_expr)
            .order_by(period_expr)
        )

        labels = []
        data = []
        for row in trend_result.all():
            labels.append(str(row[0]))
            data.append(row[1])

        return {
            "labels": labels,
            "data": data,
            "area_of_law": area_of_law,
            "court_level": court_level,
            "granularity": granularity,
            "total": sum(data),
            "trend_direction": "up" if len(data) > 1 and data[-1] > data[0] else "down" if len(data) > 1 and data[-1] < data[0] else "stable",
        }

    async def citation_heatmap(self, db: AsyncSession) -> Dict[str, Any]:
        """Citation network heatmap data."""
        # Most cited cases
        cases_result = await db.execute(
            select(Case.citation, func.count(Case.id))
            .group_by(Case.citation)
            .order_by(func.count(Case.id).desc())
            .limit(20)
        )
        most_cited_cases = [{"citation": row[0], "count": row[1]} for row in cases_result.all()]

        # Most cited statutes
        from app.models.legal import case_statutes
        statutes_result = await db.execute(
            select(case_statutes.c.statute_id, func.count(case_statutes.c.case_id))
            .group_by(case_statutes.c.statute_id)
            .order_by(func.count(case_statutes.c.case_id).desc())
            .limit(20)
        )
        most_cited_statutes = [{"statute_id": row[0], "count": row[1]} for row in statutes_result.all()]

        # Network density (from Neo4j)
        async with await get_neo4j_session() as session:
            density_result = await session.run(
                """
                MATCH (c:Case)-[:CITES]->(other:Case)
                WITH count(c) as total_citations, count(DISTINCT c) as total_cases
                RETURN toFloat(total_citations) / toFloat(total_cases * total_cases) as density
                """
            )
            density_record = await density_result.single()
            density = density_record["density"] if density_record else 0.0

        return {
            "most_cited_cases": most_cited_cases,
            "most_cited_statutes": most_cited_statutes,
            "citation_network_density": round(density, 4),
            "average_citations_per_case": round(sum(c["count"] for c in most_cited_cases) / len(most_cited_cases), 1) if most_cited_cases else 0,
        }

    async def court_performance(self, db: AsyncSession) -> Dict[str, Any]:
        """Court performance metrics."""
        # Cases by court
        court_result = await db.execute(
            select(Case.court, func.count(Case.id))
            .group_by(Case.court)
            .order_by(func.count(Case.id).desc())
        )
        cases_by_court = {row[0]: row[1] for row in court_result.all()}

        # Disposal rate
        disposed_result = await db.execute(
            select(Case.court, func.count(Case.id))
            .where(Case.status == "disposed")
            .group_by(Case.court)
        )
        disposed_by_court = {row[0]: row[1] for row in disposed_result.all()}

        disposal_rates = {}
        for court, total in cases_by_court.items():
            disposed = disposed_by_court.get(court, 0)
            disposal_rates[court] = round((disposed / total) * 100, 1) if total > 0 else 0

        return {
            "cases_by_court": cases_by_court,
            "disposal_rates": disposal_rates,
            "average_disposal_rate": round(sum(disposal_rates.values()) / len(disposal_rates), 1) if disposal_rates else 0,
        }

    async def appeal_statistics(self, db: AsyncSession) -> Dict[str, Any]:
        """Appeal success rates and trends."""
        # Appeals filed
        appeal_result = await db.execute(
            select(func.count(Case.id)).where(Case.status == "appealed")
        )
        appeals_filed = appeal_result.scalar()

        # Appeals allowed
        allowed_result = await db.execute(
            select(func.count(Case.id)).where(Case.status == "allowed")
        )
        appeals_allowed = allowed_result.scalar()

        return {
            "appeals_filed": appeals_filed,
            "appeals_allowed": appeals_allowed,
            "success_rate": round((appeals_allowed / appeals_filed) * 100, 1) if appeals_filed > 0 else 0,
        }
