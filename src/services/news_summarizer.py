"""LLM-powered summarizer for CineDigest news articles."""

import json
import re
from typing import Optional

from config.settings import get_settings
from src.utils.llm_client import LLMClient, LLMProvider
from src.utils.logging import get_logger

logger = get_logger(__name__)

_BULLET_PROMPT = """\
You are a concise film industry news summarizer. Given the title and excerpt of a movie news article, produce:
1. A punchy one-liner headline (max 12 words)
2. 3-5 bullet points capturing the key facts (start each with •)

Rules:
- Be factual, no fluff
- For leaks/rumours label them as such
- Include names (actors, directors), titles, studios when present
- Output ONLY valid JSON: {{"headline": "...", "bullets": ["...", "..."]}}

Title: {title}
Excerpt: {excerpt}
"""


class NewsSummarizer:
    """Wraps the existing LLM client to summarize news articles into bullets."""

    def __init__(self) -> None:
        settings = get_settings()
        provider = (
            LLMProvider.GROQ
            if settings.llm_provider == "groq" and settings.groq_api_key
            else LLMProvider.OLLAMA
        )
        self._client = LLMClient(
            provider=provider,
            model=getattr(settings, "groq_model_fast", None) or None,
            fallback_provider=LLMProvider.OLLAMA if provider == LLMProvider.GROQ else None,
        )

    def summarize(self, title: str, excerpt: str) -> Optional[dict]:
        """Return {"headline": str, "bullets": [str, ...]} or None on failure."""
        prompt = _BULLET_PROMPT.format(
            title=title[:300],
            excerpt=(excerpt or "")[:800],
        )
        try:
            raw = self._client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
            )
            # chat() returns a plain string
            text = raw.strip() if raw else ""
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as exc:
            logger.warning("Summarization failed for '%s': %s", title[:60], exc)
        return None
