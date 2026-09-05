import sys
import time
from db import db
from summarizer import assess_paper

def reassess_all_published():
    print("Fetching published papers from Supabase...")
    papers = db.get_published_papers(limit=50)
    print(f"Found {len(papers)} published papers.")

    for idx, paper in enumerate(papers, 1):
        arxiv_id = paper.get("arxiv_id")
        title = paper.get("title")
        print(f"\n[{idx}/{len(papers)}] Re-analyzing: {title} ({arxiv_id})...")
        
        try:
            analysis = assess_paper(paper)
            success = db.update_paper_editorial(
                arxiv_id=arxiv_id,
                status="published",
                structured_analysis=analysis
            )
            if success:
                print(f"✅ Successfully updated '{arxiv_id}' in Supabase with full flowing essay.")
            else:
                print(f"❌ Failed to update '{arxiv_id}' in Supabase.")
        except Exception as e:
            print(f"❌ Error assessing '{arxiv_id}': {e}")
        
        time.sleep(1.0)

if __name__ == "__main__":
    reassess_all_published()
