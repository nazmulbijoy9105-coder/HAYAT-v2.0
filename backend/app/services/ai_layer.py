"""
HAYAT v2.0 — AI Intelligence Layer
Layer 7: AI never invents law. It only explains, summarizes, and assists.
All outputs include source citations and disclaimers.
"""

from typing import Dict, Any, List, Optional, AsyncGenerator
import time
import json

from openai import AsyncOpenAI
from qdrant_client.models import PointStruct

from app.core.config import settings
from app.core.logging import get_logger
from app.db.qdrant import EmbeddingStore, get_qdrant_client
from app.db.redis import CacheManager
from app.db.opensearch import get_opensearch_client, INDEX_CASES, INDEX_STATUTES

logger = get_logger("hayat.ai")


class AILayer:
    """
    AI layer for legal assistance.
    Uses RAG (Retrieval-Augmented Generation) to ground all responses
    in actual legal documents from the database.
    """

    SYSTEM_PROMPT = """You are HAYAT, the Bangladesh Legal Intelligence Assistant.

CRITICAL RULES:
1. You NEVER invent laws, cases, or citations.
2. You ONLY use the provided legal documents as sources.
3. If you cannot find a relevant source, say so explicitly.
4. Always cite the specific case, statute, or section you reference.
5. Include a disclaimer that this is not legal advice.
6. For Bangladesh law, distinguish between Supreme Court Appellate Division and High Court Division precedents.
7. Note the date of any case you cite — older cases may have been overruled.
8. Be precise about section numbers and act names.

Response format:
- Direct answer first
- Supporting sources with citations
- Practical implications
- Disclaimer
"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self.embeddings = EmbeddingStore()
        self.cache = CacheManager()

    async def get_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for text."""
        if not self.client:
            raise RuntimeError("OpenAI API key not configured")

        response = await self.client.embeddings.create(
            model=settings.embedding_model,
            input=text[:8000],  # Token limit safety
        )
        return response.data[0].embedding

    async def _retrieve_context(
        self,
        query: str,
        top_k: int = 5,
        document_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant legal documents for RAG."""
        # Semantic search
        vector = await self.get_embedding(query)

        filters = {}
        if document_types:
            filters["document_type"] = document_types[0]  # Simplified

        semantic_results = await self.embeddings.search(
            vector=vector,
            limit=top_k,
            filters=filters if filters else None,
            score_threshold=0.65,
        )

        # Full-text search boost
        opensearch = get_opensearch_client()
        search_body = {
            "size": top_k,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "summary^2", "full_text", "ratio^2", "held^2"],
                }
            },
        }

        ft_results = await opensearch.search(index=INDEX_CASES, body=search_body)

        # Combine and deduplicate
        combined = []
        seen_ids = set()

        for r in semantic_results:
            if r["id"] not in seen_ids:
                combined.append({"id": r["id"], "source": "semantic", "score": r["score"], **r["payload"]})
                seen_ids.add(r["id"])

        for hit in ft_results["hits"]["hits"]:
            doc_id = hit["_id"]
            if doc_id not in seen_ids:
                combined.append({
                    "id": doc_id,
                    "source": "full_text",
                    "score": hit["_score"],
                    **hit["_source"],
                })
                seen_ids.add(doc_id)

        return combined[:top_k]

    async def generate_embedding_for_document(
        self, doc_id: str, text: str, metadata: Dict[str, Any]
    ) -> None:
        """Generate and store embedding for a legal document."""
        vector = await self.get_embedding(text)

        point = PointStruct(
            id=doc_id,
            vector=vector,
            payload={
                "doc_id": doc_id,
                "title": metadata.get("title", ""),
                "document_type": metadata.get("document_type", "unknown"),
                "court_level": metadata.get("court_level"),
                "date": metadata.get("date"),
                "area_of_law": metadata.get("area_of_law"),
            },
        )

        await self.embeddings.upsert([point])
        logger.info("embedding_stored", doc_id=doc_id, vector_size=len(vector))

    async def answer_question(
        self,
        question: str,
        context_documents: Optional[List[str]] = None,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """
        RAG-based question answering.
        Retrieves relevant documents, then generates grounded answer.
        """
        start_time = time.time()

        if not self.client:
            return {
                "question": question,
                "answer": "AI layer is not configured. Please set OPENAI_API_KEY.",
                "sources": [],
                "source_documents": [],
                "confidence": 0.0,
                "processing_time": 0.0,
            }

        # Retrieve context
        context = await self._retrieve_context(question)

        # Build prompt with context
        context_text = "\n\n".join([
            f"[Source {i+1}] {c.get('title', 'Unknown')}\n{c.get('summary', c.get('full_text', ''))[:1000]}"
            for i, c in enumerate(context)
        ])

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""Question: {question}

Relevant legal documents:
{context_text}

Please answer based ONLY on the provided documents. Cite specific cases and statutes."
            },
        ]

        response = await self.client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=temperature,
            max_tokens=settings.llm_max_tokens,
        )

        answer = response.choices[0].message.content
        processing_time = time.time() - start_time

        return {
            "question": question,
            "answer": answer,
            "sources": [
                {
                    "id": c["id"],
                    "title": c.get("title", "Unknown"),
                    "citation": c.get("citation", ""),
                    "source_type": c.get("source", "unknown"),
                    "score": c.get("score", 0),
                }
                for c in context
            ],
            "source_documents": [c["id"] for c in context],
            "confidence": min(0.95, sum(c.get("score", 0) for c in context) / max(len(context), 1)),
            "processing_time": round(processing_time, 2),
        }

    async def summarize_case(
        self,
        case_text: str,
        style: str = "detailed",
        max_length: int = 500,
    ) -> Dict[str, Any]:
        """Generate a structured case summary."""
        if not self.client:
            return {
                "summary": "AI layer not configured.",
                "key_points": [],
                "word_count": 0,
                "processing_time": 0.0,
            }

        start_time = time.time()

        style_prompts = {
            "brief": "Provide a 3-paragraph summary suitable for a quick reference.",
            "detailed": "Provide a comprehensive summary with facts, issues, reasoning, and holding.",
            "practitioner": "Focus on practical implications, relief granted, and enforcement considerations.",
            "academic": "Provide an analytical summary focusing on legal principles, ratio decidendi, and obiter dicta.",
        }

        prompt = f"""Summarize the following Bangladesh legal case.
{style_prompts.get(style, style_prompts["detailed"])}

Case text:
{case_text[:12000]}

Format:
- Summary (max {max_length} words)
- 5-7 Key Points (bullet points)
- Ratio Decidendi (if identifiable)
- Practical Implications
"""

        response = await self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1500,
        )

        content = response.choices[0].message.content

        # Extract key points (simple heuristic)
        key_points = []
        for line in content.split("\n"):
            if line.strip().startswith(("- ", "* ", "• ")):
                key_points.append(line.strip()[2:])

        return {
            "summary": content,
            "key_points": key_points[:10],
            "word_count": len(content.split()),
            "processing_time": round(time.time() - start_time, 2),
        }

    async def explain_statute(
        self,
        statute_title: str,
        section_number: str,
        section_text: str,
    ) -> Dict[str, Any]:
        """Explain a statute section in plain language."""
        if not self.client:
            return {"explanation": "AI layer not configured.", "ingredients": [], "examples": []}

        prompt = f"""Explain the following Bangladesh statute section in plain language.

Statute: {statute_title}
Section {section_number}:
{section_text}

Provide:
1. Plain language explanation (what this means in practice)
2. Legal ingredients/tests (what must be proven)
3. Common scenarios where this applies
4. Related sections or statutes
5. Important caveats or exceptions

Do NOT invent cases. If you don't know of specific cases, say so."

        response = await self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=2000,
        )

        content = response.choices[0].message.content

        return {
            "explanation": content,
            "statute": statute_title,
            "section": section_number,
        }

    async def compare_cases(self, case_texts: List[str], comparison_type: str = "full") -> Dict[str, Any]:
        """Compare multiple cases and identify similarities/differences."""
        if not self.client or len(case_texts) < 2:
            return {"comparison": "Insufficient data or AI not configured.", "similarities": [], "differences": []}

        prompt = f"""Compare the following {len(case_texts)} Bangladesh legal cases.
Focus on: {comparison_type}

"""
        for i, text in enumerate(case_texts[:3], 1):  # Limit to 3 cases
            prompt += f"Case {i}:\n{text[:4000]}\n\n"

        prompt += """
Provide:
1. Comparative analysis
2. Key similarities (bullet points)
3. Key differences (bullet points)
4. Which case is more favorable for plaintiffs/defendants and why
5. Precedential value hierarchy
"""

        response = await self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=2000,
        )

        content = response.choices[0].message.content

        # Extract similarities and differences
        similarities = []
        differences = []

        lines = content.split("\n")
        current_section = None
        for line in lines:
            if "similar" in line.lower() and ":" in line:
                current_section = "similarities"
            elif "differ" in line.lower() and ":" in line:
                current_section = "differences"
            elif line.strip().startswith(("- ", "* ", "• ")):
                if current_section == "similarities":
                    similarities.append(line.strip()[2:])
                elif current_section == "differences":
                    differences.append(line.strip()[2:])

        return {
            "comparison": content,
            "similarities": similarities[:10],
            "differences": differences[:10],
            "cases_compared": len(case_texts),
        }

    async def draft_assistance(
        self,
        document_type: str,
        facts: str,
        jurisdiction: str = "bangladesh",
        language: str = "english",
    ) -> Dict[str, Any]:
        """Assist with legal drafting based on facts and jurisdiction."""
        if not self.client:
            return {"draft": "AI layer not configured.", "suggestions": [], "cautions": []}

        prompt = f"""Assist with drafting a {document_type} for Bangladesh jurisdiction.

Facts:
{facts}

Language: {language}

Provide:
1. Suggested structure/outline
2. Key clauses to include
3. Relevant statute references (if known)
4. Common drafting mistakes to avoid
5. Jurisdiction-specific requirements

IMPORTANT: This is a drafting ASSISTANCE, not a final legal document. Always have a qualified lawyer review."

        response = await self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        return {
            "draft_assistance": response.choices[0].message.content,
            "document_type": document_type,
            "jurisdiction": jurisdiction,
            "language": language,
        }

    async def detect_conflict(
        self,
        case_text: str,
        jurisdiction: str = "bangladesh",
    ) -> Dict[str, Any]:
        """Detect potential conflicts with existing law."""
        if not self.client:
            return {"conflicts": [], "warnings": [], "analysis": "AI not configured."}

        prompt = f"""Analyze the following legal argument or position for potential conflicts with Bangladesh law.

Text:
{case_text[:8000]}

Identify:
1. Potential conflicts with statutes or constitutional provisions
2. Contradictions with established precedents (if known)
3. Jurisdictional issues
4. Procedural deficiencies
5. Areas requiring further legal research

Be conservative. Only flag conflicts you are reasonably certain about."

        response = await self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1500,
        )

        return {
            "analysis": response.choices[0].message.content,
            "conflicts_detected": True,  # Would need parsing in production
            "jurisdiction": jurisdiction,
        }
