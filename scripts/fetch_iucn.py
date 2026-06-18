"""
One-time script to fetch IUCN Red List assessments by taxonomic family
and ingest them into the Wildlife RAG knowledge base.

Usage:
    python scripts/fetch_iucn.py --family Felidae
    python scripts/fetch_iucn.py --family Ursidae --api-base https://your-app.railway.app
"""

import argparse
import asyncio
import os
import re
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

IUCN_API_BASE = "https://api.iucnredlist.org/api/v4"
IUCN_API_KEY = os.getenv("IUCN_API_KEY", "")
APP_BASE = os.getenv("API_BASE", "http://localhost:8000")

RATE_LIMIT_DELAY = 1.0  # seconds between IUCN API calls


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _assessment_to_text(assessment: dict) -> str:
    """Convert a raw IUCN assessment dict into a prose document for ingestion."""
    parts = []

    taxon = assessment.get("taxon", {}) or {}
    name = taxon.get("scientific_name", "Unknown species")

    common_names = taxon.get("common_names", []) or []
    common = next(
        (cn["name"] for cn in common_names if cn.get("main") and cn.get("language") == "eng"),
        next((cn["name"] for cn in common_names if cn.get("language") == "eng"), ""),
    )

    family = taxon.get("family_name", "")
    order = taxon.get("order_name", "")

    header = f"# {name}"
    if common:
        header += f" ({common})"
    parts.append(header)
    parts.append(f"Family: {family} | Order: {order}")

    status = assessment.get("red_list_category") or {}
    desc = status.get("description") or {}
    desc_text = desc.get("en", "") if isinstance(desc, dict) else str(desc)
    if desc_text:
        parts.append(f"\nConservation Status: {desc_text} ({status.get('code', '')})")

    trend = assessment.get("population_trend") or {}
    trend_desc = trend.get("description") or {}
    trend_text = trend_desc.get("en", "") if isinstance(trend_desc, dict) else ""
    if trend_text:
        parts.append(f"Population Trend: {trend_text}")

    doc = assessment.get("documentation") or {}
    for field, title in [
        ("rationale", "Rationale"),
        ("population", "Population"),
        ("range", "Range"),
        ("habitats", "Habitats and Ecology"),
        ("threats", "Threats"),
        ("measures", "Conservation Measures"),
        ("use_trade", "Use and Trade"),
        ("trend_justification", "Trend Justification"),
        ("taxonomic_notes", "Taxonomic Notes"),
    ]:
        content = doc.get(field)
        if content and isinstance(content, str) and content.strip():
            parts.append(f"\n## {title}\n{_strip_html(content)}")

    threats = assessment.get("threats") or []
    threat_lines = [
        f"- {t['description']['en']} ({t.get('score', '')})"
        for t in threats
        if isinstance(t.get("description"), dict) and t["description"].get("en")
    ]
    if threat_lines:
        parts.append("\n## Threat List\n" + "\n".join(threat_lines))

    habitats = assessment.get("habitats") or []
    habitat_lines = [
        f"- {h['description']['en']} (suitability: {h.get('suitability', '')})"
        for h in habitats
        if isinstance(h.get("description"), dict) and h["description"].get("en")
    ]
    if habitat_lines:
        parts.append("\n## Habitat Types\n" + "\n".join(habitat_lines))

    actions = assessment.get("conservation_actions") or []
    action_lines = [
        f"- {a['description']['en']}"
        for a in actions
        if isinstance(a.get("description"), dict) and a["description"].get("en")
    ]
    if action_lines:
        parts.append("\n## Conservation Actions\n" + "\n".join(action_lines))

    return "\n".join(parts)


async def fetch_assessments_by_family(family: str, client: httpx.AsyncClient) -> list[dict]:
    """Get latest global assessments for a taxonomic family."""
    print(f"Fetching assessment list for family: {family} ...")
    response = await client.get(
        f"{IUCN_API_BASE}/taxa/family/{family.upper()}",
        params={"latest": "true", "scope_code": "1"},
        headers={"Authorization": IUCN_API_KEY},
    )
    response.raise_for_status()
    data = response.json()
    assessments = data.get("assessments", [])
    print(f"Found {len(assessments)} assessments.")
    return assessments


async def fetch_assessment_detail(assessment_id: int, client: httpx.AsyncClient) -> dict | None:
    """Fetch full detail for a single assessment."""
    response = await client.get(
        f"{IUCN_API_BASE}/assessment/{assessment_id}",
        headers={"Authorization": IUCN_API_KEY},
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


async def ingest_text(text: str, filename: str, source: str, app_client: httpx.AsyncClient) -> None:
    """Send a text document to the RAG ingest endpoint."""
    response = await app_client.post(
        "/ingest/text",
        json={"content": text, "filename": filename, "source": source},
    )
    if response.is_success:
        data = response.json()
        print(f"  OK — {data['chunks_created']} chunks")
    elif response.status_code == 409:
        print(f"  SKIPPED — already ingested")
    else:
        print(f"  FAILED ({response.status_code}): {response.text}")


async def main(family: str) -> None:
    if not IUCN_API_KEY:
        raise SystemExit("IUCN_API_KEY environment variable is not set.")

    async with httpx.AsyncClient(timeout=30) as iucn_client:
        async with httpx.AsyncClient(base_url=APP_BASE, timeout=120) as app_client:
            assessments = await fetch_assessments_by_family(family, iucn_client)

            for i, assessment_stub in enumerate(assessments, 1):
                assessment_id = assessment_stub.get("assessment_id") or assessment_stub.get("id")
                species_name = assessment_stub.get("taxon_scientific_name", f"species_{assessment_id}")
                print(f"[{i}/{len(assessments)}] {species_name} ...", end=" ", flush=True)

                detail = await fetch_assessment_detail(assessment_id, iucn_client)
                if not detail:
                    print("NOT FOUND — skipping")
                    continue

                text = _assessment_to_text(detail)
                filename = f"iucn_{species_name.lower().replace(' ', '_')}.txt"
                await ingest_text(text, filename, "IUCN", app_client)

                time.sleep(RATE_LIMIT_DELAY)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch IUCN assessments by taxonomic family and ingest them.")
    parser.add_argument("--family", required=True, help="Taxonomic family name e.g. Felidae")
    args = parser.parse_args()
    asyncio.run(main(args.family))
