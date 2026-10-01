"""
Document and link extraction.

Responsibilities:
- Pull plain text out of an uploaded CV (PDF or DOCX).
- Pull plain text out of a LinkedIn export (PDF/DOCX) or pasted text.
- Find URLs mentioned in either document (GitHub, portfolio sites, project demos, etc).
- Fetch those URLs one level deep and extract readable text, so the LLM can see
  what the candidate's linked projects actually are.

Everything here is best-effort: a broken/unreachable link should never crash the
pipeline, it should just be noted as unavailable so the interviewer can see that
in the final summary's context.
"""

from __future__ import annotations

import os
import re
import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
import pdfplumber
import docx  # python-docx

logger = logging.getLogger(__name__)

# Domains that are noise if we try to "follow" them (trackers, share links,
# LinkedIn's own domain since we already have the profile content, etc).
SKIP_DOMAINS = {
    "linkedin.com",
    "www.linkedin.com",
    "lnkd.in",
    "l.facebook.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "mailto",
}

URL_REGEX = re.compile(r"https?://[^\s)>\]\"']+", re.IGNORECASE)

DEFAULT_TIMEOUT = int(os.getenv("LINK_FETCH_TIMEOUT_SECONDS", "8"))
DEFAULT_MAX_LINKS = int(os.getenv("MAX_LINKS_TO_FOLLOW", "6"))
MAX_CHARS_PER_PAGE = 6000


@dataclass
class FetchedLink:
    url: str
    ok: bool
    text: str = ""
    error: str = ""


@dataclass
class ResearchBundle:
    cv_text: str
    linkedin_text: str
    linked_pages: list[FetchedLink] = field(default_factory=list)

    def as_prompt_text(self) -> str:
        """Flatten everything collected into one text blob for the LLM prompt."""
        parts = [
            "=== CANDIDATE CV ===",
            self.cv_text.strip() or "(no text from the CV)",
            "",
            "=== LINKEDIN PROFILE ===",
            self.linkedin_text.strip() or "(no LinkedIn text)",
        ]
        if self.linked_pages:
            parts.append("")
            parts.append("=== CONTENT FROM LINKED PAGES (projects, GitHub, portfolio) ===")
            for link in self.linked_pages:
                parts.append(f"--- {link.url} ---")
                if link.ok:
                    parts.append(link.text.strip() or "(page is empty or contains only scripts)")
                else:
                    parts.append(f"(unavailable: {link.error})")
        return "\n".join(parts)


def extract_text_from_file(file_path: str) -> str:
    """Extract plain text from a PDF or DOCX file. Returns '' on unsupported type."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return _extract_pdf_text(file_path)
    if ext in (".docx", ".dotx"):
        return _extract_docx_text(file_path)
    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    raise ValueError(f"Unsupported file format: {ext}")


def _extract_pdf_text(file_path: str) -> str:
    chunks = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text:
                chunks.append(text)
    return "\n".join(chunks)


def _extract_docx_text(file_path: str) -> str:
    document = docx.Document(file_path)
    chunks = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            chunks.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(chunks)


def find_links(*texts: str) -> list[str]:
    """Find candidate-worth-following URLs across one or more text blobs."""
    found: list[str] = []
    seen = set()
    for text in texts:
        for match in URL_REGEX.findall(text or ""):
            url = match.rstrip(".,;:!?")
            domain = urlparse(url).netloc.lower()
            if not domain or domain in SKIP_DOMAINS:
                continue
            if url in seen:
                continue
            seen.add(url)
            found.append(url)
    return found


def fetch_link(url: str, timeout: int = DEFAULT_TIMEOUT) -> FetchedLink:
    """Fetch a single URL and return cleaned, truncated visible text."""
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; InterviewPrepBot/1.0)"},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        return FetchedLink(url=url, ok=True, text=text[:MAX_CHARS_PER_PAGE])
    except Exception as exc:  # noqa: BLE001 - deliberately broad, this is best-effort
        logger.warning("Failed to fetch %s: %s", url, exc)
        return FetchedLink(url=url, ok=False, error=str(exc))


def gather_research(
    cv_text: str,
    linkedin_text: str,
    max_links: int = DEFAULT_MAX_LINKS,
) -> ResearchBundle:
    """Build the full research bundle: CV + LinkedIn text plus one level of followed links."""
    links = find_links(cv_text, linkedin_text)[:max_links]
    fetched = [fetch_link(url) for url in links]
    return ResearchBundle(cv_text=cv_text, linkedin_text=linkedin_text, linked_pages=fetched)
