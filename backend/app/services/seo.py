import urllib.robotparser
from urllib.parse import urlparse

import requests

from ..db import db_session

# Crawlers that power AI-driven search/answer surfaces (ChatGPT browsing, Google's AI
# features, Perplexity, Claude, etc.) — as opposed to traditional search-engine crawlers
# like plain Googlebot/Bingbot, which sites already almost always allow.
AI_CRAWLERS = [
    ("GPTBot", "OpenAI — used to train/update ChatGPT"),
    ("ChatGPT-User", "OpenAI — live browsing when a ChatGPT user asks it to visit a page"),
    ("Google-Extended", "Google — Gemini / AI Overviews training and grounding"),
    ("Applebot-Extended", "Apple — Apple Intelligence features"),
    ("ClaudeBot", "Anthropic — Claude training/browsing"),
    ("PerplexityBot", "Perplexity — answer-engine crawling"),
    ("CCBot", "Common Crawl — a dataset many AI models are trained on"),
    ("Bytespider", "ByteDance — used for its AI products"),
    ("Amazonbot", "Amazon — Alexa/AI features"),
]


def generate_faq_schema() -> dict:
    """Build a schema.org FAQPage JSON-LD object from approved FAQs. Search engines and AI
    answer surfaces (Google AI Overviews, ChatGPT/Perplexity browsing) parse this directly —
    it's the single highest-leverage discoverability signal for content we already have
    structured, at zero additional cost."""
    with db_session() as conn:
        rows = conn.execute("SELECT question, answer FROM faqs ORDER BY priority DESC, id ASC").fetchall()

    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": r["question"],
                "acceptedAnswer": {"@type": "Answer", "text": r["answer"]},
            }
            for r in rows
        ],
    }


def check_ai_crawler_access(website_url: str) -> list:
    """Check the site's robots.txt against known AI crawlers. Returns a list of
    {bot, description, allowed} — a client can't show up in ChatGPT/Perplexity/AI Overviews
    answers if their own robots.txt blocks the crawler that would index them for it."""
    if not website_url:
        return []

    url = website_url if website_url.startswith("http") else f"https://{website_url}"
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    try:
        resp = requests.get(robots_url, timeout=8)
        if resp.status_code == 404:
            # No robots.txt at all means everything is allowed by default.
            return [{"bot": bot, "description": desc, "allowed": True} for bot, desc in AI_CRAWLERS]
        resp.raise_for_status()
    except requests.RequestException:
        return []

    rp = urllib.robotparser.RobotFileParser()
    rp.parse(resp.text.splitlines())

    site_root = f"{parsed.scheme}://{parsed.netloc}/"
    return [{"bot": bot, "description": desc, "allowed": rp.can_fetch(bot, site_root)} for bot, desc in AI_CRAWLERS]
