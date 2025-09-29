import feedparser
from datetime import datetime, timedelta
import time
import requests
import json
import re

# Define arXiv search query
TOPICS = [
    "large language model", "transformer", "RLHF", "multimodal LLM", "LLM reasoning", 
    "LLM alignment", "retrieval augmented generation", "foundation model"
]

BASE_URL = "http://export.arxiv.org/api/query?"
ARXIV_CATEGORIES = ["cs.CL", "cs.LG", "cs.AI", "stat.ML"]
EXCLUDE_KEYWORDS = ["3d", "point cloud", "rgb-d", "reconstruction", "scene", "geometry"]

# High-impact organizations to boost paper scores
HIGH_IMPACT_ORGS = [
    "Google", "DeepMind", "Anthropic", "OpenAI", "Microsoft", "Meta", "Facebook",
    "Stanford", "MIT", "Berkeley", "CMU", "NYU", "Toronto", "Oxford", "Cambridge"
]

def is_relevant(paper):
    """Filter out irrelevant papers based on keywords"""
    title = paper["title"].lower()
    summary = paper.get("summary", "").lower()
    return not any(bad in title or bad in summary for bad in EXCLUDE_KEYWORDS)

def has_trending_keywords(title, abstract):
    """Check if paper has trending/high-impact keywords"""
    trending_keywords = [
        'gpt', 'llm', 'large language model', 'transformer', 'attention',
        'diffusion', 'stable diffusion', 'text-to-image', 'multimodal',
        'reinforcement learning', 'rlhf', 'constitutional ai', 'alignment',
        'few-shot', 'zero-shot', 'in-context learning', 'prompt',
        'retrieval augmented', 'rag', 'vector database', 'embedding',
        'fine-tuning', 'instruction tuning', 'chain-of-thought',
        'reasoning', 'planning', 'agent', 'autonomous', 'tool use',
        'code generation', 'copilot', 'programming', 'software engineering',
        'computer vision', 'object detection', 'image segmentation',
        'neural architecture search', 'efficient', 'compression', 'quantization',
        'federated learning', 'privacy', 'differential privacy',
        'graph neural network', 'knowledge graph', 'recommendation',
        'time series', 'forecasting', 'anomaly detection',
        'adversarial', 'robustness', 'interpretability', 'explainable ai'
    ]
    
    text = (title + " " + abstract).lower()
    return any(keyword in text for keyword in trending_keywords)

def extract_arxiv_id(url_or_id):
    """Extract arXiv ID from various formats"""
    if not url_or_id:
        return None
    
    # Handle direct ID
    if re.match(r'^\d{4}\.\d{4,5}(v\d+)?$', url_or_id):
        return url_or_id
    
    # Handle URLs
    match = re.search(r'(\d{4}\.\d{4,5})(v\d+)?', url_or_id)
    return match.group(0) if match else None

def count_versions(arxiv_id):
    """Get number of versions for an arXiv paper"""
    if not arxiv_id:
        return 1
    
    try:
        # Query arXiv API for paper details
        url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            feed = feedparser.parse(response.text)
            if feed.entries:
                # Check if version info is in the ID
                entry_id = feed.entries[0].id
                version_match = re.search(r'v(\d+)$', entry_id)
                return int(version_match.group(1)) if version_match else 1
    except requests.RequestException:
        pass
    return 1

def has_high_impact_authors(authors):
    """Check if paper has authors from high-impact organizations"""
    author_text = " ".join(authors).lower()
    return any(org.lower() in author_text for org in HIGH_IMPACT_ORGS)



def fetch_recent_papers_by_topic():
    """Fetch recent papers from arXiv by topic"""
    all_papers = []
    
    for topic in TOPICS:
        print(f"Fetching papers for: {topic}")
        
        # Build query for this topic
        query = f"all:{topic.replace(' ', '+')}"
        url = f"{BASE_URL}search_query={query}&sortBy=submittedDate&sortOrder=descending&max_results=10"
        
        try:
            feed = feedparser.parse(url)
            
            for entry in feed.entries:
                arxiv_id = extract_arxiv_id(entry.id)
                
                # Check if paper is recent (last 14 days)
                published_date = datetime.strptime(entry.published, "%Y-%m-%dT%H:%M:%SZ")
                days_ago = (datetime.now() - published_date).days
                
                if days_ago > 14:  # Skip papers older than 2 weeks
                    continue
                
                paper = {
                    "title": entry.title,
                    "summary": entry.summary,
                    "link": entry.link,
                    "pdf_url": next((l.href for l in entry.links if l.type == "application/pdf"), None),
                    "published": entry.published,
                    "authors": [author.name for author in entry.authors],
                    "topic": topic,
                    "arxiv_id": arxiv_id,
                    "days_since_publication": days_ago
                }
                
                if is_relevant(paper):
                    all_papers.append(paper)
            
            # Small delay between topics
            time.sleep(1)
            
        except Exception as e:
            print(f"Error fetching {topic}: {e}")
            continue
    
    return all_papers

def rank_papers(papers):
    """
    Rank recent arXiv papers based on relevance and quality heuristics.
    Goal: fewer, better papers (high precision curation).
    """

    # === Configurable weights ===
    weights = {
        'versions': 1.0,          # multiple revisions = more iteration/interest
        'high_impact_authors': 2.0,
        'benchmark': 1.0,
        'open_source': 1.0,
        'trending_keywords': 2.0, # strong match to hot LLM-related ideas
        'topic_overlap': 1.5,
        'recency': 1.0
    }

    topics = [
        "large language model", "multimodal", 
        "reasoning", "retrieval augmented", "transformer"
    ]
    
    blacklist_terms = [
        "power transformer", "signal transformer", 
        "circuit", "motor", "control system"
    ]

    for paper in papers:
        score = 0
        title = paper.get('title', '').strip()
        abstract = paper.get('summary', '').lower()
        authors = paper.get('authors', [])
        days_old = paper.get('days_since_publication', 14)
        arxiv_id = paper.get('arxiv_id')

        # === 1. Filter out irrelevant papers early ===
        if any(b in abstract for b in blacklist_terms):
            paper['score'] = 0
            paper['reason'] = "blacklisted"
            continue

        # === 2. Versions (more = refinement or traction) ===
        num_versions = count_versions(arxiv_id)
        if num_versions > 1:
            score += weights['versions']
            print(f" +{weights['versions']} for versions: {title[:60]}... ({num_versions} versions)")

        # === 3. High-impact authors or affiliations ===
        if has_high_impact_authors(authors):
            score += weights['high_impact_authors']
            print(f" +{weights['high_impact_authors']} for high-impact authors: {title[:60]}...")

        # === 4. Benchmark mentions ===
        if 'benchmark' in abstract:
            score += weights['benchmark']
            print(f" +{weights['benchmark']} for benchmark: {title[:60]}...")

        # === 5. Open-source mentions ===
        if 'open-source' in abstract or 'open source' in abstract:
            score += weights['open_source']
            print(f" +{weights['open_source']} for open-source: {title[:60]}...")

        # === 6. Trending LLM-related keywords ===
        if has_trending_keywords(title, abstract):
            score += weights['trending_keywords']
            print(f" +{weights['trending_keywords']} for trending keywords: {title[:60]}...")

        # === 7. Topic overlap bonus ===
        topic_hits = sum(t in abstract for t in topics)
        if topic_hits >= 2:
            score += weights['topic_overlap']
            print(f" +{weights['topic_overlap']} for multi-topic relevance: {title[:60]}...")

        # === 8. Recency (mild freshness boost) ===
        if days_old <= 3:
            score += weights['recency']
            print(f" +{weights['recency']} for very recent: {title[:60]}... ({days_old} days)")
        elif days_old <= 7:
            score += weights['recency'] * 0.5
            print(f" +{weights['recency'] * 0.5} for recent: {title[:60]}... ({days_old} days)")

        # === 9. Damp recency if overall weak ===
        if score < 2:
            score *= 0.8  # weak papers shouldn't ride recency bonus

        paper['score'] = round(score, 2)
        paper['reason'] = "ranked"
        print(f"Total Score: {paper['score']} | {title[:60]}...")

    # === 10. Final sort and selection ===
    ranked = [p for p in papers if p.get('reason') == 'ranked']
    ranked_sorted = sorted(ranked, key=lambda x: x.get('score', 0), reverse=True)
    top_papers = ranked_sorted[:10]

    print("\n=== Top Papers ===")
    for p in top_papers:
        print(f"{p['score']:>4}  |  {p['title'][:80]}")

    return top_papers


def remove_duplicates(papers):
    """Remove duplicate papers based on title similarity"""
    unique_papers = []
    seen_titles = set()
    
    for paper in papers:
        title_key = paper['title'].lower().strip()
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_papers.append(paper)
    
    return unique_papers

def fetch_daily_papers():
    """Main function to fetch and rank papers"""
    print("Fetching trending papers...")
    
    all_papers = []
    
    # Fetch recent papers by topic (our primary method)
    topic_papers = fetch_recent_papers_by_topic()
    if topic_papers:
        print(f"Found {len(topic_papers)} papers from topic search")
        all_papers.extend(topic_papers)
    
    # Remove duplicates
    all_papers = remove_duplicates(all_papers)
    print(f"After deduplication: {len(all_papers)} papers")
    
    # Rank papers
    print("\\nRanking papers...")
    ranked_papers = rank_papers(all_papers)
    
    # Return top papers
    top_papers = ranked_papers[:15]  # Top 15 papers
    print(f"\\nReturning top {len(top_papers)} papers")
    
    return top_papers

# For backwards compatibility
def _fetch_daily_papers():
    """Legacy function - use fetch_daily_papers() instead"""
    return fetch_daily_papers()

if __name__ == "__main__":
    papers = fetch_daily_papers()
    
    print("\\n" + "="*80)
    print("TOP RANKED PAPERS")
    print("="*80)
    
    for i, paper in enumerate(papers, 1):
        print(f"\\n{i}. {paper['title']}")
        print(f"   Score: {paper.get('score', 0)}")
        print(f"   Topic: {paper.get('topic', 'N/A')}")
        print(f"   Authors: {', '.join(paper.get('authors', [])[:3])}{'...' if len(paper.get('authors', [])) > 3 else ''}")
        print(f"   Published: {paper.get('published', 'N/A')}")
        print(f"   Link: {paper.get('link', 'N/A')}")
        print(f"   Abstract: {paper.get('summary', '')[:200]}...")