import feedparser
from datetime import datetime, timedelta

# Define arXiv search query
# TOPICS = [
#     "large language model", "transformer", "rlhf",
#      "alignment", "interpretability", "in-context learning", "multimodal LLM", "LLM reasoning", 
#      "LLM alignment", "retrieval augmented generation"
# ]

TOPICS = [
    "large language model", "transformer", "rlhf", "multimodal LLM", "LLM reasoning", 
     "LLM alignment", "retrieval augmented generation"
]

BASE_URL = "http://export.arxiv.org/api/query?"

ARXIV_CATEGORIES = ["cs.CL", "cs.LG", "cs.AI", "stat.ML"]

EXCLUDE_KEYWORDS = ["3d", "point cloud", "rgb-d", "reconstruction", "scene", "geometry"]

def is_relevant(paper):
    title = paper["title"].lower()
    summary = paper["summary"].lower()
    return not any(bad in title or bad in summary for bad in EXCLUDE_KEYWORDS)


def build_query(title_keywords, categories, max_results=5):
	topic_part = "+OR+".join(f"ti:{kw.replace(' ', '+')}" for kw in title_keywords)
	category_part = "+OR+".join(f"cat:{cat}" for cat in categories)
	full_query = f"({topic_part})+AND+({category_part})"
	return f"{BASE_URL}search_query={full_query}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"


import feedparser
import requests
import time
from datetime import datetime

def fetch_top_papers_semantic_scholar():
    """
    Use Semantic Scholar API to get top papers by citation count
    This is the most reliable method for getting truly "top" papers
    """
    SS_API_BASE = "https://api.semanticscholar.org/graph/v1"
    
    all_top_papers = []
    
    for topic in TOPICS:
        print(f"Fetching top papers for: {topic}")
        
        # Search for papers on this topic, sorted by citation count
        search_url = f"{SS_API_BASE}/paper/search"
        params = {
            "query": topic,
            "limit": 10,  # Reduced from 20 to be more conservative
            "fields": "title,abstract,url,citationCount,year,authors,externalIds,venue",
            "sort": "citationCount:desc"  # Sort by citation count (highest first)
        }
        
        # Add retry logic for rate limiting
        max_retries = 3
        retry_delay = 5  # Start with 5 seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.get(search_url, params=params)
                
                if response.status_code == 429:  # Rate limited
                    if attempt < max_retries - 1:
                        print(f"   Rate limited, waiting {retry_delay} seconds before retry {attempt + 1}/{max_retries}")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        print(f"   Max retries reached for topic: {topic}")
                        break
                        
                elif response.status_code == 200:
                    data = response.json()
                    
                    topic_papers = []
                    for paper in data.get('data', []):
                        # Check if paper has arXiv ID
                        external_ids = paper.get('externalIds', {})
                        if external_ids and external_ids.get('ArXiv'):
                            arxiv_id = external_ids['ArXiv']
                            arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"
                            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                            
                            topic_papers.append({
                                "title": paper['title'],
                                "summary": paper.get('abstract', ''),
                                "link": arxiv_url,
                                "pdf_url": pdf_url,
                                "published": str(paper.get('year', '')),
                                "authors": [author['name'] for author in paper.get('authors', [])],
                                "citation_count": paper.get('citationCount', 0),
                                "topic": topic,
                                "venue": paper.get('venue', '')
                            })
                    
                    # Take top 3-5 papers per topic
                    topic_papers.sort(key=lambda x: x['citation_count'], reverse=True)
                    #all_top_papers.extend(topic_papers[:3])  # Top 3 per topic
                    all_top_papers.extend(topic_papers[:2])  # Top 2 per topic
                    
                    # Success - break out of retry loop
                    break
                    
                else:
                    print(f"   Error fetching data for {topic}: {response.status_code}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        break
                        
            except Exception as e:
                print(f"   Error processing {topic}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    break
        
        # Rate limiting between topics - increased from 1 to 3 seconds
        time.sleep(3)
    
    # Sort all papers by citation count and return top ones
    all_top_papers.sort(key=lambda x: x['citation_count'], reverse=True)
    return all_top_papers[:10]  # Return top 10 overall

def fetch_top_papers_crossref():
    """
    Alternative approach using CrossRef API
    Good for getting citation data, but may have fewer arXiv papers
    """
    import requests
    
    all_papers = []
    
    for topic in TOPICS:
        # CrossRef API search
        url = "https://api.crossref.org/works"
        params = {
            "query": topic,
            "rows": 20,
            "sort": "is-referenced-by-count",  # Sort by citation count
            "order": "desc"
        }
        
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                
                for item in data['message']['items']:
                    # Look for arXiv papers
                    if 'URL' in item:
                        for url in item['URL']:
                            if 'arxiv.org' in url:
                                paper_id = url.split('/')[-1]
                                all_papers.append({
                                    "title": item['title'][0] if item.get('title') else '',
                                    "summary": item.get('abstract', ''),
                                    "link": f"https://arxiv.org/abs/{paper_id}",
                                    "pdf_url": f"https://arxiv.org/pdf/{paper_id}.pdf",
                                    "published": item.get('published-print', {}).get('date-parts', [['']])[0][0],
                                    "authors": [f"{author.get('given', '')} {author.get('family', '')}" 
                                              for author in item.get('author', [])],
                                    "citation_count": item.get('is-referenced-by-count', 0),
                                    "topic": topic
                                })
                                break
            
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            print(f"Error with CrossRef for {topic}: {e}")
            continue
    
    # Sort by citation count
    all_papers.sort(key=lambda x: x['citation_count'], reverse=True)
    return all_papers[:10]

def fetch_top_papers_arxiv_enhanced():
    """
    Enhanced arXiv approach: fetch more papers and use external citation data
    """
    # First, get a larger set of papers from arXiv
    papers_by_topic = {}
    
    for topic in TOPICS:
        # Search with broader parameters
        search_query = f"all:{topic}"
        query_url = f"http://export.arxiv.org/api/query?search_query={search_query}&max_results=50&sortBy=submittedDate&sortOrder=descending"
        
        feed = feedparser.parse(query_url)
        
        topic_papers = []
        for entry in feed.entries:
            topic_papers.append({
                "title": entry.title,
                "summary": entry.summary,
                "link": entry.link,
                "pdf_url": next((l.href for l in entry.links if l.type == "application/pdf"), None),
                "published": entry.published,
                "authors": [author.name for author in entry.authors],
                "topic": topic,
                "arxiv_id": entry.id.split('/')[-1]
            })
        
        papers_by_topic[topic] = topic_papers
    
    # Now enrich with citation data from Semantic Scholar
    all_papers = []
    for topic, papers in papers_by_topic.items():
        for paper in papers[:10]:  # Check top 10 per topic
            try:
                # Get citation data from Semantic Scholar
                ss_url = f"https://api.semanticscholar.org/graph/v1/paper/ARXIV:{paper['arxiv_id']}"
                ss_params = {"fields": "citationCount,influentialCitationCount"}
                
                ss_response = requests.get(ss_url, params=ss_params)
                if ss_response.status_code == 200:
                    ss_data = ss_response.json()
                    paper['citation_count'] = ss_data.get('citationCount', 0)
                    paper['influential_citation_count'] = ss_data.get('influentialCitationCount', 0)
                else:
                    paper['citation_count'] = 0
                    paper['influential_citation_count'] = 0
                
                all_papers.append(paper)
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                print(f"Error getting citation data for {paper['title']}: {e}")
                paper['citation_count'] = 0
                all_papers.append(paper)
    
    # Sort by citation count
    all_papers.sort(key=lambda x: x['citation_count'], reverse=True)
    return all_papers[:10]

def fetch_trending_papers_fortnight():
    """
    Fetch papers trending in the last 14 days
    Uses arXiv for recent papers + Semantic Scholar for citation velocity
    """
    from datetime import datetime, timedelta
    
    # Calculate date range (last 14 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=14)
    
    # Format dates for arXiv API (YYYYMMDD format)
    start_date_str = start_date.strftime("%Y%m%d")
    end_date_str = end_date.strftime("%Y%m%d")
    
    print(f"Fetching trending papers from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    all_trending_papers = []
    SS_API_BASE = "https://api.semanticscholar.org/graph/v1"
    
    for topic in TOPICS:
        print(f"  Searching for: {topic}")
        
        # Build arXiv query with date filtering
        topic_query = topic.replace(' ', '+')
        query = f"all:{topic_query}+AND+submittedDate:[{start_date_str}+TO+{end_date_str}]"
        
        # Search arXiv for recent papers
        arxiv_url = f"{BASE_URL}search_query={query}&sortBy=submittedDate&sortOrder=descending&max_results=20"
        
        try:
            feed = feedparser.parse(arxiv_url)
            topic_papers = []
            
            for entry in feed.entries:
                # Extract arXiv ID
                arxiv_id = entry.id.split('/')[-1]
                
                # Get paper details
                paper_data = {
                    "title": entry.title,
                    "summary": entry.summary,
                    "link": entry.link,
                    "pdf_url": next((l.href for l in entry.links if l.type == "application/pdf"), None),
                    "published": entry.published,
                    "authors": [author.name for author in entry.authors],
                    "topic": topic,
                    "arxiv_id": arxiv_id
                }
                
                # Calculate days since publication
                pub_date = datetime.strptime(entry.published, "%Y-%m-%dT%H:%M:%SZ")
                days_since_pub = (datetime.now() - pub_date).days
                days_since_pub = max(1, days_since_pub)  # Avoid division by zero
                
                paper_data["days_since_publication"] = days_since_pub
                topic_papers.append(paper_data)
            
            # Enrich with Semantic Scholar citation data
            for paper in topic_papers[:10]:  # Limit to avoid rate limiting
                try:
                    # Get citation data from Semantic Scholar
                    ss_url = f"{SS_API_BASE}/paper/ARXIV:{paper['arxiv_id']}"
                    ss_params = {"fields": "citationCount,influentialCitationCount"}
                    
                    response = requests.get(ss_url, params=ss_params, timeout=10)
                    if response.status_code == 200:
                        ss_data = response.json()
                        citation_count = ss_data.get('citationCount', 0)
                        paper['citation_count'] = citation_count
                        
                        # Calculate trend score (citations per day)
                        trend_score = citation_count / paper['days_since_publication']
                        paper['trend_score'] = trend_score
                    else:
                        paper['citation_count'] = 0
                        paper['trend_score'] = 0
                    
                    # Small delay to be nice to the API
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"    Error getting citation data for {paper['title'][:50]}: {e}")
                    paper['citation_count'] = 0
                    paper['trend_score'] = 0
            
            all_trending_papers.extend(topic_papers)
            
            # Delay between topics
            time.sleep(2)
            
        except Exception as e:
            print(f"  Error processing {topic}: {e}")
            continue
    
    # Sort by trend score (citations per day) - this is the key trending metric
    all_trending_papers.sort(key=lambda x: x['trend_score'], reverse=True)
    
    # If we don't have enough papers, fall back to broader date range
    if len(all_trending_papers) < 5:
        print("Not enough recent papers, expanding to last 30 days...")
        # You could implement a 30-day fallback here if needed
    
    print(f"Found {len(all_trending_papers)} trending papers")
    return all_trending_papers[:15]  # Return top 15 trending papers

# Main function - choose your preferred approach
def fetch_daily_papers():
    """
    Modified function to get trending papers from the last 14 days
    """
    print("Fetching trending papers from the last fortnight...")
    
    # Method 1: Trending papers (Primary method)
    try:
        return fetch_trending_papers_fortnight()
    except Exception as e:
        print(f"Trending papers failed: {e}")
        
    # Method 2: Fallback to Semantic Scholar top papers
    try:
        print("Falling back to top cited papers...")
        return fetch_top_papers_semantic_scholar()
    except Exception as e:
        print(f"Semantic Scholar failed: {e}")
        
    # Method 3: Final fallback - just recent papers
    print("Falling back to recent papers...")
    query_url = build_query(TOPICS, ARXIV_CATEGORIES, max_results=10)
    feed = feedparser.parse(query_url)
    
    papers = []
    for entry in feed.entries:
        papers.append({
            "title": entry.title,
            "summary": entry.summary,
            "link": entry.link,
            "pdf_url": next((l.href for l in entry.links if l.type == "application/pdf"), None),
            "published": entry.published,
            "authors": [author.name for author in entry.authors],
            "citation_count": 0  # Unknown
        })
    
    return papers

# Optional: Add citation threshold filtering
def filter_high_impact_papers(papers, min_citations=100):
    """
    Filter papers to only include those with high citation counts
    """
    return [p for p in papers if p.get('citation_count', 0) >= min_citations]


def _fetch_daily_papers():
    query_url = build_query(TOPICS, ARXIV_CATEGORIES, max_results=10)
	#query_url = build_query(TOPICS, max_results=5)
    feed = feedparser.parse(query_url)

    papers = []
    for entry in feed.entries:
        papers.append({
            "title": entry.title,
            "summary": entry.summary,
            "link": entry.link,
            "pdf_url": next((l.href for l in entry.links if l.type == "application/pdf"), None),
            "published": entry.published,
            "authors": [author.name for author in entry.authors]
        })
    return papers

# Example usage
if __name__ == "__main__":
    #raw_papers = fetch_filtered_papers()
    raw_papers = fetch_daily_papers()
    papers = [p for p in raw_papers if is_relevant(p)]
    for i, p in enumerate(papers):
        print(f"\n{i+1}. {p['title']}")
        print(f"Published: {p['published']}")
        print(f"Authors: {', '.join(p['authors'])}")
        
        # Show trending metrics if available
        if 'trend_score' in p:
            print(f"Trend Score: {p['trend_score']:.3f} (citations/day)")
            print(f"Citations: {p.get('citation_count', 0)}")
            print(f"Days since publication: {p.get('days_since_publication', 'N/A')}")
        
        print(f"PDF: {p['pdf_url']}")
        print(f"Link: {p['link']}")
        print(f"Abstract: {p['summary'][:300]}...\n")

