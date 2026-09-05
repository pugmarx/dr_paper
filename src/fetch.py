import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import feedparser
import requests

from config import config

# arXiv Search Topics & Configurations
TOPICS = [
    "large language model", "transformer", "RLHF", "multimodal LLM", 
    "LLM reasoning", "LLM alignment", "retrieval augmented generation", 
    "foundation model", "autonomous agent", "code generation"
]

ARXIV_BASE_URL = "http://export.arxiv.org/api/query?"
HF_DAILY_PAPERS_URL = "https://huggingface.co/api/daily_papers"
SUBSTACK_NEWSLETTER_FEEDS = [
    "https://lastweekinai.substack.com/feed",
    "https://importai.substack.com/feed"
]

# High-impact organizations to boost paper scores
HIGH_IMPACT_ORGS = [
    "google", "deepmind", "anthropic", "openai", "microsoft", "meta", "facebook",
    "hugging face", "huggingface", "stanford", "mit", "berkeley", "cmu", "nyu", 
    "toronto", "oxford", "cambridge", "princeton", "washington", "allen institute"
]

# Blacklist terms to filter out non-AI domains
BLACKLIST_TERMS = [
    "power transformer", "signal transformer", "circuit", "motor", 
    "control system", "point cloud", "rgb-d", "reconstruction", 
    "scene reconstruction", "vlog", "surveillance"
]

# High-impact keywords in AI/LLM research
TRENDING_KEYWORDS = [
    'gpt', 'llm', 'large language model', 'transformer', 'attention',
    'diffusion', 'text-to-image', 'multimodal', 'vision-language',
    'reinforcement learning', 'rlhf', 'rlaif', 'alignment',
    'few-shot', 'zero-shot', 'in-context learning', 'prompt',
    'retrieval augmented', 'rag', 'vector database', 'embedding',
    'fine-tuning', 'instruction tuning', 'chain-of-thought',
    'reasoning', 'planning', 'agent', 'autonomous', 'tool use',
    'code generation', 'software engineering', 'quantization',
    'speculative decoding', 'long context', 'mixture of experts', 'moe',
    'interpretability', 'mechanistic interpretability', 'benchmark'
]

def extract_arxiv_id_and_version(url_or_id: str) -> tuple[Optional[str], int]:
    """Extract arXiv base ID and version number from string without extra network requests."""
    if not url_or_id:
        return None, 1
    
    match = re.search(r'(\d{4}\.\d{4,5})(?:v(\d+))?', url_or_id)
    if match:
        base_id = match.group(1)
        version = int(match.group(2)) if match.group(2) else 1
        return base_id, version
    return None, 1

def get_current_edition_tag() -> str:
    """Return the current ISO week tag e.g. '2026-W36'"""
    now = datetime.utcnow()
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"

def has_high_impact_authors(authors: List[str]) -> bool:
    """Check if any author belongs to a top institution"""
    author_text = " ".join(authors).lower()
    return any(org in author_text for org in HIGH_IMPACT_ORGS)

def is_blacklisted(title: str, summary: str) -> bool:
    """Check if paper contains blacklisted domain terms"""
    combined = f"{title} {summary}".lower()
    return any(term in combined for term in BLACKLIST_TERMS)

def calculate_paper_score(paper: Dict) -> float:
    """
    Calculate quality and relevance score for weekly curation.
    """
    title = paper.get("title", "").strip()
    summary = paper.get("summary", "").strip()
    authors = paper.get("authors", [])
    combined_text = f"{title} {summary}".lower()
    days_old = paper.get("days_since_publication", 7)
    version = paper.get("version", 1)
    
    if is_blacklisted(title, summary):
        return 0.0

    score = 0.0

    # 1. Newsletter curation bonus (+3.0 if highlighted by Substack/newsletters)
    if paper.get("curated_source") in ("lastweekinai", "substack"):
        score += 3.0

    # 2. High impact institution (+2.0)
    if has_high_impact_authors(authors):
        score += 2.0

    # 3. Paper revisions / traction (+1.0 for version > 1)
    if version > 1:
        score += 1.0

    # 4. Trending keywords (+2.0 for 2+ keywords, +1.0 for 1 keyword)
    keyword_hits = sum(1 for kw in TRENDING_KEYWORDS if kw in combined_text)
    if keyword_hits >= 2:
        score += 2.0
    elif keyword_hits == 1:
        score += 1.0

    # 5. Benchmark or open-source release (+1.0)
    if "benchmark" in combined_text or "open source" in combined_text or "open-source" in combined_text:
        score += 1.0

    # 6. Core topic overlap bonus
    core_topics = ["large language model", "multimodal", "reasoning", "retrieval augmented", "transformer", "agent"]
    topic_hits = sum(1 for t in core_topics if t in combined_text)
    if topic_hits >= 2:
        score += 1.5
    elif topic_hits == 1:
        score += 0.5

    # 7. Recency bonus
    if days_old <= 3:
        score += 1.0
    elif days_old <= 7:
        score += 0.5

    # 8. Upvotes bonus (if from Hugging Face Daily Papers)
    upvotes = paper.get("upvotes", 0)
    if upvotes > 0:
        score += min(upvotes * 0.2, 3.0)

    # 9. Damp weak papers
    if score < 2.5 and paper.get("curated_source") not in ("lastweekinai", "huggingface"):
        score *= 0.75

    return round(score, 2)

def fetch_newsletter_curated_arxiv_ids() -> Set[str]:
    """Scrape recent newsletter RSS feeds to find curated arXiv paper mentions"""
    curated_ids = set()
    
    for feed_url in SUBSTACK_NEWSLETTER_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                content = getattr(entry, "summary", "") + " " + getattr(entry, "content", [{}])[0].get("value", "")
                # Find all arxiv IDs or links in the newsletter content
                matches = re.findall(r'(?:arxiv\.org/(?:abs|pdf)/|arXiv:)(\d{4}\.\d{4,5})', content, re.IGNORECASE)
                for aid in matches:
                    curated_ids.add(aid)
        except Exception as e:
            print(f"[WARN] Failed parsing newsletter feed {feed_url}: {e}")

    return curated_ids

def fetch_arxiv_papers(topics: Optional[List[str]] = None, days_back: int = 7) -> List[Dict]:
    """Fetch papers from arXiv across specified AI topics within the weekly window"""
    topics_to_search = topics or TOPICS
    all_papers = []
    newsletter_ids = fetch_newsletter_curated_arxiv_ids()

    for topic in topics_to_search:
        query = f"all:{topic.replace(' ', '+')}"
        url = f"{ARXIV_BASE_URL}search_query={query}&sortBy=submittedDate&sortOrder=descending&max_results=10"
        
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                arxiv_id, version = extract_arxiv_id_and_version(entry.id)
                if not arxiv_id:
                    continue

                try:
                    published_dt = datetime.strptime(entry.published, "%Y-%m-%dT%H:%M:%SZ")
                    days_ago = (datetime.utcnow() - published_dt).days
                except Exception:
                    published_dt = datetime.utcnow()
                    days_ago = 0

                if days_ago > days_back:
                    continue

                pdf_link = next((l.href for l in getattr(entry, "links", []) if getattr(l, "type", "") == "application/pdf"), f"https://arxiv.org/pdf/{arxiv_id}.pdf")
                clean_title = re.sub(r'\s+', ' ', entry.title).strip()
                clean_summary = re.sub(r'\s+', ' ', entry.summary).strip()
                author_names = [a.name for a in getattr(entry, "authors", []) if hasattr(a, "name")]

                is_in_newsletter = arxiv_id in newsletter_ids

                paper = {
                    "arxiv_id": arxiv_id,
                    "version": version,
                    "title": clean_title,
                    "summary": clean_summary,
                    "authors": author_names,
                    "topic": topic,
                    "published_at": published_dt.isoformat() + "Z",
                    "days_since_publication": days_ago,
                    "pdf_url": pdf_link,
                    "hf_url": f"https://huggingface.co/papers/{arxiv_id}",
                    "curated_source": "lastweekinai" if is_in_newsletter else "arxiv",
                    "published_edition": get_current_edition_tag(),
                    "upvotes": 0,
                    "status": "draft"
                }
                all_papers.append(paper)

            time.sleep(0.5)
        except Exception as e:
            print(f"[WARN] Error querying arXiv for topic '{topic}': {e}")
            continue

    return all_papers

def fetch_hf_daily_papers(limit: int = 15) -> List[Dict]:
    """Fetch curated trending daily papers from Hugging Face API"""
    papers = []
    try:
        response = requests.get(HF_DAILY_PAPERS_URL, timeout=10)
        if response.status_code != 200:
            return papers

        data = response.json()
        for item in data[:limit]:
            paper_info = item.get("paper", {})
            raw_id = paper_info.get("id", "")
            arxiv_id, version = extract_arxiv_id_and_version(raw_id)
            if not arxiv_id:
                continue

            published_str = paper_info.get("publishedAt", "")
            try:
                published_dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                days_ago = (datetime.utcnow().replace(tzinfo=published_dt.tzinfo) - published_dt).days
            except Exception:
                published_dt = datetime.utcnow()
                days_ago = 0

            authors = [a.get("name", "") for a in paper_info.get("authors", []) if isinstance(a, dict)]
            clean_title = re.sub(r'\s+', ' ', paper_info.get("title", "")).strip()
            clean_summary = re.sub(r'\s+', ' ', paper_info.get("summary", "")).strip()

            if clean_title:
                papers.append({
                    "arxiv_id": arxiv_id,
                    "version": version,
                    "title": clean_title,
                    "summary": clean_summary,
                    "authors": authors,
                    "topic": "Trending AI",
                    "published_at": published_dt.isoformat(),
                    "days_since_publication": days_ago,
                    "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                    "hf_url": f"https://huggingface.co/papers/{arxiv_id}",
                    "curated_source": "huggingface",
                    "published_edition": get_current_edition_tag(),
                    "upvotes": paper_info.get("upvotes", 0),
                    "status": "draft"
                })
    except Exception as e:
        print(f"[WARN] Error querying Hugging Face Daily Papers: {e}")

    return papers

def deduplicate_papers(papers: List[Dict]) -> List[Dict]:
    """Deduplicate papers preferring higher-signal entries (newsletter / HF with upvotes)"""
    seen_ids = set()
    seen_titles = set()
    unique = []

    # Sort priority: newsletter mentions > upvotes > versions
    def priority_key(x):
        is_news = 100 if x.get("curated_source") == "lastweekinai" else 0
        return (is_news + x.get("upvotes", 0), x.get("version", 1))

    sorted_papers = sorted(papers, key=priority_key, reverse=True)

    for p in sorted_papers:
        aid = p.get("arxiv_id")
        title_key = re.sub(r'[^a-zA-Z0-9]', '', p.get("title", "").lower())
        
        if aid and aid in seen_ids:
            continue
        if title_key in seen_titles:
            continue

        if aid:
            seen_ids.add(aid)
        seen_titles.add(title_key)
        unique.append(p)

    return unique

def fetch_weekly_candidate_papers(limit: int = 10, days_back: int = 7) -> List[Dict]:
    """
    Main curation fetcher: Ingests from newsletters, Hugging Face, and arXiv for the weekly edition.
    """
    all_papers = []

    # 1. HF Daily Papers
    hf_papers = fetch_hf_daily_papers()
    all_papers.extend(hf_papers)

    # 2. arXiv Papers (with newsletter cross-checking)
    arxiv_papers = fetch_arxiv_papers(days_back=days_back)
    all_papers.extend(arxiv_papers)

    # 3. Deduplicate
    unique_papers = deduplicate_papers(all_papers)

    # 4. Score and filter
    scored_papers = []
    for paper in unique_papers:
        score = calculate_paper_score(paper)
        paper["score"] = score
        scored_papers.append(paper)

    scored_papers.sort(key=lambda x: x["score"], reverse=True)
    return scored_papers[:limit]

# Backwards compatible alias
def fetch_and_rank_papers(include_arxiv: bool = True, include_hf: bool = True, min_score: Optional[float] = None, limit: Optional[int] = None) -> List[Dict]:
    return fetch_weekly_candidate_papers(limit=limit or 10)

if __name__ == "__main__":
    print("[*] Fetching weekly candidate papers...")
    top_candidates = fetch_weekly_candidate_papers(limit=5)
    print(f"\n[+] Selected {len(top_candidates)} top candidate papers:")
    for idx, p in enumerate(top_candidates, 1):
        print(f"\n{idx}. [{p['score']:>4.1f}] {p['title']}")
        print(f"   arXiv: {p['arxiv_id']} | Source: {p['curated_source']} | Edition: {p['published_edition']}")
        print(f"   Abstract: {p['summary'][:160]}...")