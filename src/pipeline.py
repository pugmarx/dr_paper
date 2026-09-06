#!/usr/bin/env python3
"""
Dr. Paper: Weekly Research Curation & Editorial Review Pipeline
Provides weekly ingestion into Supabase staging (status='draft'),
interactive editorial review, and static publishing.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from config import config
from fetch import fetch_weekly_candidate_papers
from summarizer import assess_paper
from db import db

def run_dry_run(limit: int = 10):
    """Fetch and score top weekly candidate papers without LLM calls or DB writes"""
    print("=" * 70)
    print(f"🔬 Dr. Paper: Weekly Candidate Dry Run (Limit: {limit})")
    print("=" * 70)

    start_time = time.time()
    papers = fetch_weekly_candidate_papers(limit=limit)
    elapsed = time.time() - start_time

    print(f"\n[+] Fetched and scored {len(papers)} weekly candidates in {elapsed:.2f}s:\n")
    for idx, p in enumerate(papers, 1):
        print(f"{idx}. [{p['score']:>4.1f}] {p['title']}")
        print(f"    arXiv: {p['arxiv_id']} | Source: {p['curated_source']} | Edition: {p['published_edition']}")
        print(f"    Authors: {', '.join(p['authors'][:3])}{' et al.' if len(p['authors']) > 3 else ''}")
        print(f"    Abstract: {p['summary'][:160]}...\n")

    print("[*] Dry run completed. No LLM calls or database writes were performed.")
    return papers

def run_local(limit: int = 3, output_json: Optional[str] = "docs/papers.json"):
    """Run weekly ingestion and LLM assessment locally without writing to Supabase"""
    print("=" * 70)
    print(f"🧪 Dr. Paper: Local Testing Mode (LLM Provider: {config.LLM_PROVIDER})")
    print("=" * 70)

    papers = fetch_weekly_candidate_papers(limit=limit)
    if not papers:
        print("[!] No papers found matching criteria.")
        return []

    print(f"\n[+] Assessing {len(papers)} candidate papers with cloud LLM...")
    processed_papers = []

    for idx, p in enumerate(papers, 1):
        print(f"\n[{idx}/{len(papers)}] Assessing: {p['title'][:60]}...")
        analysis = assess_paper(p)
        p["structured_analysis"] = analysis
        p["status"] = "published"  # For local testing preview

        print(f"   💡 Problem:    {analysis.get('problem')}")
        print(f"   ⚙️ Innovation: {analysis.get('innovation')}")
        print(f"   🚀 Impact:     {analysis.get('impact')}")
        print(f"   📌 Takeaways:  {', '.join(analysis.get('key_takeaways', []))}")
        
        processed_papers.append(p)

    if output_json:
        out_path = Path(output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        export_data = {
            "metadata": {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "total_papers": len(processed_papers),
                "topics": sorted(list({p.get("topic", "General") for p in processed_papers}))
            },
            "papers": processed_papers
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        print(f"\n[+] Saved local output snapshot to {out_path}")

    return processed_papers

def run_ingest(limit: int = 10, auto_publish: bool = False):
    """Weekly Ingestion: Fetches, drafts AI assessments, and saves to Supabase (status='draft' or 'published')"""
    target_status = "published" if auto_publish else "draft"
    print("=" * 70)
    print(f"📥 Dr. Paper: Weekly Ingestion Pipeline (Schema: {config.SUPABASE_SCHEMA} | Target: {target_status})")
    print("=" * 70)

    if not db.is_configured():
        print("[ERROR] Supabase is not configured. Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")
        sys.exit(1)

    start_time = time.time()
    run_id = db.start_run_log(metadata={"action": "weekly_ingest", "limit": limit, "auto_publish": auto_publish, "llm_provider": config.LLM_PROVIDER})
    
    try:
        # 1. Fetch weekly candidates
        candidates = fetch_weekly_candidate_papers(limit=limit)
        fetched_count = len(candidates)
        print(f"[+] Fetched {fetched_count} high-signal candidate papers.")

        if not candidates:
            print("[*] No new papers found.")
            db.complete_run_log(run_id, status="success", fetched=0, duration_ms=int((time.time() - start_time) * 1000))
            return

        # 2. Check existing in database
        arxiv_ids = [p["arxiv_id"] for p in candidates if p.get("arxiv_id")]
        existing_ids = db.get_existing_arxiv_ids(arxiv_ids)
        new_papers = [p for p in candidates if p["arxiv_id"] not in existing_ids]
        skipped_count = len(candidates) - len(new_papers)
        print(f"[*] Found {len(existing_ids)} already in database. {len(new_papers)} new papers to assess.")

        # 3. Assess only new candidate papers
        llm_calls = 0
        for idx, paper in enumerate(new_papers, 1):
            print(f"   [{idx}/{len(new_papers)}] Assessing: {paper['title'][:55]}...")
            analysis = assess_paper(paper)
            paper["structured_analysis"] = analysis
            paper["status"] = target_status
            llm_calls += 1
            time.sleep(1.0)

        # 4. Upsert papers to Supabase
        if new_papers:
            print(f"\n[*] Saving {len(new_papers)} papers to Supabase '{config.SUPABASE_SCHEMA}.papers' (status='{target_status}')...")
            res = db.batch_upsert_papers(new_papers, default_status=target_status)
            if res.get("success"):
                print(f"[SUCCESS] Saved {res.get('count')} papers!")
            else:
                print(f"[ERROR] Failed to save papers: {res.get('error')}")
                raise RuntimeError(f"Database upsert failed: {res.get('error')}")

        duration_ms = int((time.time() - start_time) * 1000)
        db.complete_run_log(
            run_id=run_id,
            status="success",
            fetched=fetched_count,
            added=len(new_papers),
            skipped=skipped_count,
            duration_ms=duration_ms,
            llm_calls=llm_calls
        )

        print("\n" + "=" * 70)
        if auto_publish:
            print(f"✅ Ingestion complete. {len(new_papers)} new papers published to Dr. Paper live.")
        else:
            print(f"✅ Ingestion complete. Run 'python src/pipeline.py --review' to moderate drafts.")
        print("=" * 70)

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        print(f"\n[ERROR] Ingestion failed: {e}")
        db.complete_run_log(run_id, status="failed", duration_ms=duration_ms, error_message=str(e))
        sys.exit(1)

def run_review():
    """Interactive CLI Editorial Review: Moderate, edit, and publish draft papers"""
    print("=" * 70)
    print(f"📰 Dr. Paper: Editorial Moderation & Review (Schema: {config.SUPABASE_SCHEMA})")
    print("=" * 70)

    if not db.is_configured():
        print("[ERROR] Supabase is not configured.")
        sys.exit(1)

    drafts = db.get_pending_drafts(limit=25)
    if not drafts:
        print("\n[+] No pending drafts found in database! All caught up.")
        return

    print(f"\n[+] Found {len(drafts)} pending drafts for editorial review.\n")
    
    published_count = 0
    rejected_count = 0

    for idx, paper in enumerate(drafts, 1):
        arxiv_id = paper.get("arxiv_id")
        title = paper.get("title")
        score = paper.get("score", 0.0)
        source = paper.get("curated_source", "arxiv")
        edition = paper.get("published_edition", "")
        analysis = paper.get("structured_analysis", {})

        print("=" * 80)
        print(f"[{idx}/{len(drafts)}] DRAFT: {title}")
        print(f"arXiv: {arxiv_id} | Score: {score} | Source: {source} | Edition: {edition}")
        print("-" * 80)
        
        hook = analysis.get('one_line_hook') or analysis.get('problem')
        context = analysis.get('context_and_motivation') or analysis.get('problem')
        mechanism = analysis.get('core_mechanism') or analysis.get('innovation')
        results = analysis.get('empirical_results') or analysis.get('impact')
        critique = analysis.get('critique_and_tradeoffs')
        takeaways = analysis.get('key_takeaways', [])

        if hook:
            print(f"🎯 THESIS HOOK:\n   {hook}\n")
        if context:
            print(f"📖 CONTEXT & MOTIVATION:\n   {context}\n")
        if mechanism:
            print(f"⚙️ CORE MECHANISM:\n   {mechanism}\n")
        if results:
            print(f"📊 EMPIRICAL FINDINGS:\n   {results}\n")
        if critique:
            print(f"🧐 CRITIQUE & TRADEOFFS:\n   {critique}\n")
        if takeaways:
            print(f"📌 KEY TAKEAWAYS:\n   • " + "\n   • ".join(takeaways) + "\n")
        print("-" * 80)

        while True:
            choice = input("Action [P]ublish | [N]ote & Publish | [F]eature & Publish | [R]eject | [S]kip | [Q]uit: ").strip().lower()

            if choice in ("p", "publish"):
                db.update_paper_editorial(arxiv_id, status="published")
                print(f"✅ Published: {arxiv_id}\n")
                published_count += 1
                break
            elif choice in ("n", "note"):
                note = input("\nEnter Curator's Note (1-2 sentences on why you picked this / key takeaway): ").strip()
                db.update_paper_editorial(arxiv_id, status="published", editorial_notes=note if note else None)
                print(f"✅ Published with Curator Note: {arxiv_id}\n")
                published_count += 1
                break
            elif choice in ("f", "feature"):
                note = input("\nOptional Curator's Note for Featured Pick (press Enter to skip): ").strip()
                db.update_paper_editorial(arxiv_id, status="published", is_featured=True, editorial_notes=note if note else None)
                print(f"⭐ Featured & Published: {arxiv_id}\n")
                published_count += 1
                break
            elif choice in ("r", "reject"):
                db.update_paper_editorial(arxiv_id, status="rejected")
                print(f"❌ Rejected: {arxiv_id}\n")
                rejected_count += 1
                break
            elif choice in ("s", "skip"):
                print(f"⏭️ Skipped: {arxiv_id}\n")
                break
            elif choice in ("q", "quit"):
                print("\n[!] Exiting review session.")
                return
            else:
                print("Invalid choice. Please enter P, N, F, R, S, or Q.")

    print("=" * 70)
    print(f"🎉 Review session complete: {published_count} Published, {rejected_count} Rejected.")
    print("=" * 70)

def run_publish_single(arxiv_id: str):
    """Quickly promote a single arXiv ID to published"""
    if not db.is_configured():
        print("[ERROR] Supabase is not configured.")
        return
    
    success = db.update_paper_editorial(arxiv_id, status="published")
    if success:
        print(f"✅ Successfully published paper '{arxiv_id}'!")
    else:
        print(f"❌ Failed to publish paper '{arxiv_id}'.")

def main():
    parser = argparse.ArgumentParser(description="Dr. Paper: Weekly Research Curation & Editorial Review")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and score weekly candidates without LLM/DB writes")
    parser.add_argument("--local", action="store_true", help="Run local testing and output to docs/papers.json")
    parser.add_argument("--ingest", action="store_true", help="Fetch and draft top weekly candidates to Supabase (status='draft')")
    parser.add_argument("--sync", action="store_true", help="Alias for --ingest")
    parser.add_argument("--auto-publish", action="store_true", help="Publish directly to live site (status='published') during ingestion")
    parser.add_argument("--review", action="store_true", help="Launch interactive CLI review to moderate and publish drafts")
    parser.add_argument("--publish", type=str, metavar="ARXIV_ID", help="Publish a specific paper by arXiv ID")
    parser.add_argument("--export-published", action="store_true", help="Export published papers to docs/papers.json")
    parser.add_argument("--test-db", action="store_true", help="Test connection to Supabase dr_paper schema")
    parser.add_argument("--limit", type=int, default=10, help="Candidate paper limit (default: 10)")

    args = parser.parse_args()

    if args.test_db:
        success, msg = db.test_connection()
        print(f"[{'SUCCESS' if success else 'ERROR'}] {msg}")
        sys.exit(0 if success else 1)

    if args.dry_run:
        run_dry_run(limit=args.limit)
    elif args.local:
        run_local(limit=args.limit)
    elif args.ingest or args.sync:
        run_ingest(limit=args.limit, auto_publish=args.auto_publish)
    elif args.review:
        run_review()
    elif args.publish:
        run_publish_single(args.publish)
    elif args.export_published:
        export_published_snapshot()
    else:
        print("[!] No mode specified. Use --help to see all commands.")
        run_dry_run(limit=args.limit)

if __name__ == "__main__":
    main()
