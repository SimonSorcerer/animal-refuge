"""Ingest all documents from the /documents directory."""

import asyncio
import sys
from pathlib import Path

import httpx

API_BASE = "http://localhost:8000"
DOCUMENTS_DIR = Path(__file__).parent.parent / "documents"

SOURCE_MAP: dict[str, str] = {
    "iucn": "IUCN",
    "wwf": "WWF",
    "cites": "CITES",
}

def _guess_source(filename: str) -> str:
    lower = filename.lower()
    for key, value in SOURCE_MAP.items():
        if key in lower:
            return value
    return ""


async def seed() -> None:
    files = [f for f in DOCUMENTS_DIR.iterdir() if f.suffix.lower() in {".pdf", ".txt"}]
    if not files:
        print(f"No PDF or TXT files found in {DOCUMENTS_DIR}")
        sys.exit(1)

    async with httpx.AsyncClient(base_url=API_BASE, timeout=120) as client:
        for path in sorted(files):
            print(f"Ingesting {path.name} ...", end=" ", flush=True)
            with path.open("rb") as fh:
                response = await client.post(
                    "/ingest",
                    files={"file": (path.name, fh, "application/octet-stream")},
                    data={"source": _guess_source(path.name)},
                )
            if response.is_success:
                data = response.json()
                print(f"OK — {data['chunks_created']} chunks")
            elif response.status_code == 409:
                print(f"SKIPPED — already ingested")
            else:
                print(f"FAILED ({response.status_code}): {response.text}")


if __name__ == "__main__":
    asyncio.run(seed())
