import math
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import feedparser
import requests

from config import config

# arXiv Search Topics & Configurations (Computer Science AI/ML categories)
TOPICS = [
    "reasoning", "agent", "world model", "kv cache", "attention",
    "rlvr", "synthetic data", "test-time compute", "coding agent",
    "multimodal", "post-training", "distillation"
]

ARXIV_BASE_URL = "http://export.arxiv.org/api/query?"
HF_DAILY_PAPERS_URL = "https://huggingface.co/api/daily_papers"

# High-impact organizations, frontier labs, and academic research hubs
HIGH_IMPACT_ORGS = [
    # Frontier & Open Source AI Pioneers
    "openai", "anthropic", "google", "deepmind", "meta", "fair", "microsoft",
    "hugging face", "huggingface", "fast.ai", "fastai", "mistral", "together ai",
    "cohere", "stability ai", "eleutherai", "deepseek", "qwen", "01.ai", "allenai",
    "allen institute", "tokenrhythm",

    # Industry Research Labs
    "salesforce", "nvidia", "apple", "amazon science", "ibm research", "tencent",
    "alibaba", "bytedance", "baidu research", "huawei",

    # Global Top Academic & Research Institutions
    "stanford", "mit", "berkeley", "cmu", "carnegie mellon", "harvard", "princeton",
    "cornell", "columbia", "nyu", "uiuc", "illinois", "washington", "toronto", "mila",
    "vector institute", "oxford", "cambridge", "imperial", "eth zurich", "epfl",
    "inria", "max planck", "tsinghua", "peking", "kaist", "skku", "nus", "tokyo",
    "apodex"
]

# Blacklist terms to filter out non-AI and niche biological/clinical domains
BLACKLIST_TERMS = [
    "power transformer", "signal transformer", "circuit", "motor", 
    "control system", "point cloud", "rgb-d", "reconstruction", 
    "scene reconstruction", "vlog", "surveillance", "cell segmentation",
    "histopathology", "cytology", "ct scan", "mri segmentation",
    "ultrasound", "microscopy", "colonoscopy", "fluid dynamics",
    "battery", "power grid", "lesion detection", "tumor segmentation"
]

# Frontier paradigms & high-signal research keywords
TRENDING_KEYWORDS = [
    # Reasoning & Test-time Compute
    "reasoning", "test-time compute", "test-time scaling", "rlvr", "process supervision",
    "self-play", "chain-of-thought", "search-based", "tree search",
    # KV Cache & Efficient Attention
    "kv cache", "attention sparsification", "declarative attention", "sparse attention",
    "linear attention", "long-context", "long context", "context compression",
    # Agents & World Models
    "world model", "coding agent", "swe-bench", "software engineering agent",
    "gui agent", "autonomous agent", "tool use", "scientific workflow",
    # Synthetic Data & Alignment
    "synthetic data", "distillation", "verifiable rewards", "post-training",
    "rlhf", "rlaif", "dpo", "grpo", "preference optimization",
    # Frontier Architectures & Latent Space
    "mixture of experts", "moe", "multimodal", "vision-language", "latent space",
    "discrete diffusion", "quantization", "speculative decoding", "mechanistic interpretability"
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

def has_high_impact_authors(authors: List[str], org: Optional[str] = None, text: str = "") -> bool:
    """Check if any author, organization, or context matches high-impact research institutions"""
    combined_target = (f"{org or ''} {' '.join(authors)} {text}").lower()
    return any(target_org in combined_target for target_org in HIGH_IMPACT_ORGS)

def is_blacklisted(title: str, summary: str) -> bool:
    """Check if paper contains blacklisted domain terms"""
    combined = f"{title} {summary}".lower()
    return any(term in combined for term in BLACKLIST_TERMS)

def calculate_paper_score(paper: Dict) -> float:
    """
    Calculate quality and relevance score for weekly/rolling curation.
    Combines logarithmic community traction, frontier paradigm alignment,
    institutional pedigree, and open benchmark releases.
    """
    title = paper.get("title", "").strip()
    summary = paper.get("summary", "").strip()
    authors = paper.get("authors", [])
    org = paper.get("organization", "")
    upvotes = paper.get("upvotes", 0)
    version = paper.get("version", 1)
    days_old = paper.get("days_since_publication", 7)
    combined_text = f"{title} {summary}".lower()
    
    if is_blacklisted(title, summary):
        return 0.0

    score = 0.0

    # 1. Logarithmic Community Traction (Upvotes / Peer Attention)
    # 400 upvotes -> +8.99 pts | 100 upvotes -> +6.92 pts | 10 upvotes -> +3.60 pts
    if upvotes > 0:
        score += math.log(1 + upvotes) * 1.5

    # 2. Institutional Pedigree & Frontier Lab Boost (+2.5 pts)
    if has_high_impact_authors(authors, org=org, text=combined_text):
        score += 2.5

    # 3. Frontier Paradigm Keyword Hits (up to +4.0 pts)
    keyword_hits = sum(1 for kw in TRENDING_KEYWORDS if kw in combined_text)
    score += min(keyword_hits * 0.8, 4.0)

    # 4. Benchmark / Open Evaluation Platform / Dataset Release (+1.5 pts)
    eval_indicators = ["benchmark", "evaluation platform", "dataset", "open source", "open-source", "harness"]
    if any(ind in combined_text for ind in eval_indicators):
        score += 1.5

    # 5. Paper Revisions / Multi-iteration Traction (+1.0 pt for version > 1)
    if version > 1:
        score += 1.0

    # 6. Recency Adjustment (Peak rolling sweet-spot is 1-5 days old)
    if days_old <= 3:
        score += 1.0
    elif days_old <= 7:
        score += 0.5

    # 7. Curated Source Boost
    if paper.get("curated_source") in ("huggingface", "lastweekinai", "substack"):
        score += 1.0

    # 8. Damp weak unvetted preprints
    if score < 3.0 and upvotes == 0 and not has_high_impact_authors(authors, org=org, text=combined_text):
        score *= 0.7

    return round(score, 2)

def fetch_hf_daily_papers(days_back: int = 7) -> List[Dict]:
    """
    Fetch all curated trending papers from Hugging Face API across the full rolling window.
    Iterates over each date in the window to capture mature peer signals.
    """
    all_papers = []
    seen_ids = set()

    for day_offset in range(days_back):
        target_date = datetime.utcnow() - timedelta(days=day_offset)
        date_str = target_date.strftime("%Y-%m-%d")
        url = f"{HF_DAILY_PAPERS_URL}?date={date_str}"
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                continue

            data = response.json()
            for item in data:
                paper_info = item.get("paper", {})
                raw_id = paper_info.get("id", "")
                arxiv_id, version = extract_arxiv_id_and_version(raw_id)
                if not arxiv_id or arxiv_id in seen_ids:
                    continue

                seen_ids.add(arxiv_id)

                published_str = paper_info.get("publishedAt", "")
                try:
                    published_dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                    days_ago = (datetime.utcnow().replace(tzinfo=published_dt.tzinfo) - published_dt).days
                except Exception:
                    published_dt = target_date
                    days_ago = day_offset

                authors = [a.get("name", "") for a in paper_info.get("authors", []) if isinstance(a, dict)]
                clean_title = re.sub(r'\s+', ' ', paper_info.get("title", "")).strip()
                clean_summary = re.sub(r'\s+', ' ', paper_info.get("summary", "")).strip()
                org_info = paper_info.get("organization") or {}
                org_name = org_info.get("name") if isinstance(org_info, dict) else ""

                if clean_title and not is_blacklisted(clean_title, clean_summary):
                    all_papers.append({
                        "arxiv_id": arxiv_id,
                        "version": version,
                        "title": clean_title,
                        "summary": clean_summary,
                        "authors": authors,
                        "organization": org_name or "",
                        "topic": "Frontier AI",
                        "published_at": published_dt.isoformat(),
                        "days_since_publication": max(days_ago, 0),
                        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                        "hf_url": f"https://huggingface.co/papers/{arxiv_id}",
                        "curated_source": "huggingface",
                        "published_edition": get_current_edition_tag(),
                        "upvotes": paper_info.get("upvotes", 0),
                        "status": "draft"
                    })
        except Exception as e:
            print(f"[WARN] Error querying Hugging Face Daily Papers for date {date_str}: {e}")

    return all_papers

def fetch_arxiv_papers(topics: Optional[List[str]] = None, days_back: int = 7) -> List[Dict]:
    """Fetch recent papers from arXiv across specified frontier AI topics within the rolling window"""
    topics_to_search = topics or TOPICS
    all_papers = []
    headers = {"User-Agent": "DrPaperBot/1.0 (https://drpaper.pugmarx.me; contact@pugmarx.me)"}

    for topic in topics_to_search[:5]:
        topic_term = topic.replace(' ', '+')
        query = f"(cat:cs.CL+OR+cat:cs.AI+OR+cat:cs.LG)+AND+(ti:%22{topic_term}%22+OR+abs:%22{topic_term}%22)"
        url = f"{ARXIV_BASE_URL}search_query={query}&sortBy=submittedDate&sortOrder=descending&max_results=10"
        
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code != 200:
                continue
            feed = feedparser.parse(res.content)
            for entry in feed.entries:
                arxiv_id, version = extract_arxiv_id_and_version(entry.id)
                if not arxiv_id:
                    continue

                clean_title = re.sub(r'\s+', ' ', entry.title).strip()
                clean_summary = re.sub(r'\s+', ' ', entry.summary).strip()

                if is_blacklisted(clean_title, clean_summary):
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
                author_names = [a.name for a in getattr(entry, "authors", []) if hasattr(a, "name")]

                paper = {
                    "arxiv_id": arxiv_id,
                    "version": version,
                    "title": clean_title,
                    "summary": clean_summary,
                    "authors": author_names,
                    "organization": "",
                    "topic": topic,
                    "published_at": published_dt.isoformat() + "Z",
                    "days_since_publication": days_ago,
                    "pdf_url": pdf_link,
                    "hf_url": f"https://huggingface.co/papers/{arxiv_id}",
                    "curated_source": "arxiv",
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

def deduplicate_papers(papers: List[Dict]) -> List[Dict]:
    """Deduplicate papers preferring higher-signal entries (upvotes, verified metadata, versions)"""
    seen_ids = set()
    seen_titles = set()
    unique = []

    # Sort priority: upvotes > versions > has_organization
    def priority_key(x):
        has_org = 10 if x.get("organization") else 0
        return (x.get("upvotes", 0), has_org, x.get("version", 1))

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

def fetch_rolling_candidate_papers(limit: int = 15, days_back: int = 7) -> List[Dict]:
    """
    Main curation fetcher: Ingests candidates across the 7-day rolling window,
    scores with logarithmic community traction and frontier paradigm matching,
    and returns top-ranked breakthrough papers.
    """
    all_papers = []

    # 1. Multi-day HF Daily Papers (Community peer signals & upvotes across 7 days)
    hf_papers = fetch_hf_daily_papers(days_back=days_back)
    all_papers.extend(hf_papers)

    # 2. arXiv Category Papers (Fallback preprints when pool needs supplementary candidates)
    if len(all_papers) < limit * 3:
        arxiv_papers = fetch_arxiv_papers(days_back=days_back)
        all_papers.extend(arxiv_papers)

    # 3. Deduplicate
    unique_papers = deduplicate_papers(all_papers)

    # 4. Score and rank
    scored_papers = []
    for paper in unique_papers:
        score = calculate_paper_score(paper)
        paper["score"] = score
        scored_papers.append(paper)

    scored_papers.sort(key=lambda x: x["score"], reverse=True)
    return scored_papers[:limit]

# Backwards compatible aliases
def fetch_weekly_candidate_papers(limit: int = 10, days_back: int = 7) -> List[Dict]:
    return fetch_rolling_candidate_papers(limit=limit, days_back=days_back)

def fetch_and_rank_papers(include_arxiv: bool = True, include_hf: bool = True, min_score: Optional[float] = None, limit: Optional[int] = None) -> List[Dict]:
    return fetch_rolling_candidate_papers(limit=limit or 10)

if __name__ == "__main__":
    print("[*] Fetching candidate papers across 7-day rolling window with new discovery logic...")
    top_candidates = fetch_rolling_candidate_papers(limit=8)
    print(f"\n[+] Selected {len(top_candidates)} top candidate papers:")
    for idx, p in enumerate(top_candidates, 1):
        print(f"\n{idx}. [{p['score']:>4.1f} pts | {p['upvotes']:>3} upvotes | Org: {p.get('organization') or 'N/A'}] {p['title']}")
        print(f"   arXiv: {p['arxiv_id']} | Source: {p['curated_source']} | Edition: {p['published_edition']}")
        print(f"   Abstract: {p['summary'][:140]}...")