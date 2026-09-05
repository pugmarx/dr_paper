import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Set
import requests

from config import config

class SupabaseClient:
    def __init__(self):
        self.base_url = config.SUPABASE_URL
        self.service_key = config.SUPABASE_SECRET_KEY or config.SUPABASE_ANON_KEY
        self.anon_key = config.SUPABASE_ANON_KEY
        self.schema = config.SUPABASE_SCHEMA
        
        self.rest_url = f"{self.base_url}/rest/v1"
        self.headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
            "Accept-Profile": self.schema,
            "Content-Profile": self.schema,
            "Prefer": "return=representation"
        }

    def is_configured(self) -> bool:
        """Check if Supabase credentials are provided"""
        return bool(self.base_url and self.service_key)

    def test_connection(self) -> tuple[bool, str]:
        """Test connection to dr_paper schema in Supabase"""
        if not self.is_configured():
            return False, "Supabase credentials not configured (SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing)"
        
        try:
            url = f"{self.rest_url}/papers?select=count"
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code in (200, 206):
                return True, f"Connection successful to schema '{self.schema}'!"
            return False, f"HTTP {resp.status_code}: {resp.text}"
        except Exception as e:
            return False, f"Connection error: {e}"

    def get_existing_arxiv_ids(self, arxiv_ids: List[str]) -> Set[str]:
        """Check which arXiv IDs already exist in the database with a single query"""
        if not self.is_configured() or not arxiv_ids:
            return set()

        try:
            formatted_ids = ",".join(f'"{aid}"' for aid in arxiv_ids)
            url = f"{self.rest_url}/papers?select=arxiv_id&arxiv_id=in.({formatted_ids})"
            resp = requests.get(url, headers=self.headers, timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
                return {item["arxiv_id"] for item in data if "arxiv_id" in item}
        except Exception as e:
            print(f"[WARN] Error checking existing arXiv IDs: {e}")

        return set()

    def batch_upsert_papers(self, papers: List[Dict], default_status: str = "draft") -> Dict:
        """Batch upsert candidate papers as drafts into dr_paper.papers"""
        if not self.is_configured():
            return {"success": False, "count": 0, "error": "Supabase not configured"}

        if not papers:
            return {"success": True, "count": 0}

        records = []
        for p in papers:
            record = {
                "arxiv_id": p.get("arxiv_id"),
                "title": p.get("title"),
                "authors": p.get("authors", []),
                "summary": p.get("summary", ""),
                "structured_analysis": p.get("structured_analysis", {}),
                "topic": p.get("topic", "General"),
                "score": float(p.get("score", 0.0)),
                "pdf_url": p.get("pdf_url"),
                "hf_url": p.get("hf_url"),
                "status": p.get("status", default_status),
                "is_featured": bool(p.get("is_featured", False)),
                "editorial_notes": p.get("editorial_notes"),
                "curated_source": p.get("curated_source", "arxiv"),
                "published_edition": p.get("published_edition"),
                "published_at": p.get("published_at")
            }
            records.append(record)

        headers = {
            **self.headers,
            "Prefer": "resolution=merge-duplicates,return=representation"
        }

        try:
            url = f"{self.rest_url}/papers"
            resp = requests.post(url, headers=headers, json=records, timeout=30)
            if resp.status_code in (200, 201):
                inserted = resp.json()
                return {"success": True, "count": len(inserted)}
            return {"success": False, "count": 0, "error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"success": False, "count": 0, "error": str(e)}

    def get_pending_drafts(self, limit: int = 20) -> List[Dict]:
        """Fetch papers with status='draft' for editorial review"""
        if not self.is_configured():
            return []

        try:
            url = f"{self.rest_url}/papers?status=eq.draft&order=score.desc&limit={limit}"
            resp = requests.get(url, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"[WARN] Error fetching pending drafts: {e}")
        return []

    def get_published_papers(self, limit: int = 50) -> List[Dict]:
        """Fetch papers with status='published'"""
        if not self.is_configured():
            return []

        try:
            url = f"{self.rest_url}/papers?status=eq.published&order=published_at.desc&limit={limit}"
            resp = requests.get(url, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"[WARN] Error fetching published papers: {e}")
        return []

    def update_paper_editorial(
        self, 
        arxiv_id: str, 
        status: str, 
        editorial_notes: Optional[str] = None, 
        is_featured: Optional[bool] = None,
        structured_analysis: Optional[Dict] = None
    ) -> bool:
        """Update paper status (e.g. 'published' / 'rejected') and optional editorial notes"""
        if not self.is_configured():
            return False

        payload = {"status": status, "updated_at": datetime.utcnow().isoformat() + "Z"}
        if editorial_notes is not None:
            payload["editorial_notes"] = editorial_notes
        if is_featured is not None:
            payload["is_featured"] = is_featured
        if structured_analysis is not None:
            payload["structured_analysis"] = structured_analysis

        try:
            url = f"{self.rest_url}/papers?arxiv_id=eq.{arxiv_id}"
            resp = requests.patch(url, headers=self.headers, json=payload, timeout=10)
            return resp.status_code in (200, 204)
        except Exception as e:
            print(f"[WARN] Error updating paper {arxiv_id}: {e}")
            return False

    def start_run_log(self, metadata: Optional[Dict] = None) -> Optional[str]:
        """Start a telemetry run log in dr_paper.runs"""
        if not self.is_configured():
            return None

        record = {
            "started_at": datetime.utcnow().isoformat() + "Z",
            "status": "running",
            "metadata": metadata or {}
        }

        try:
            url = f"{self.rest_url}/runs"
            resp = requests.post(url, headers=self.headers, json=record, timeout=10)
            if resp.status_code in (200, 201):
                data = resp.json()
                if data and isinstance(data, list):
                    return data[0].get("id")
        except Exception as e:
            print(f"[WARN] Failed to create run log: {e}")
        return None

    def complete_run_log(
        self, 
        run_id: Optional[str], 
        status: str, 
        fetched: int = 0, 
        added: int = 0, 
        skipped: int = 0, 
        duration_ms: int = 0, 
        llm_calls: int = 0, 
        error_message: Optional[str] = None
    ):
        """Complete a telemetry run log in dr_paper.runs"""
        if not self.is_configured() or not run_id:
            return

        payload = {
            "completed_at": datetime.utcnow().isoformat() + "Z",
            "status": status,
            "papers_fetched": fetched,
            "papers_added": added,
            "papers_skipped": skipped,
            "duration_ms": duration_ms,
            "llm_calls": llm_calls,
            "error_message": error_message
        }

        try:
            url = f"{self.rest_url}/runs?id=eq.{run_id}"
            requests.patch(url, headers=self.headers, json=payload, timeout=10)
        except Exception as e:
            print(f"[WARN] Failed to update run log: {e}")

db = SupabaseClient()
