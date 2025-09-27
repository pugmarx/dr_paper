#!/usr/bin/env python3
"""
Notion to Website Generator
Fetches papers from Notion database and generates JSON for GitHub Pages
"""

import requests
import json
import os
import sys
from datetime import datetime
from pathlib import Path

class NotionToWebsite:
    def __init__(self, integration_token, database_id):
        """Initialize with Notion credentials"""
        self.token = integration_token
        self.database_id = database_id
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {integration_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
    
    def fetch_all_papers(self):
        """Fetch all papers from Notion database"""
        url = f"{self.base_url}/databases/{self.database_id}/query"
        
        papers = []
        has_more = True
        start_cursor = None
        
        while has_more:
            payload = {"page_size": 100}
            if start_cursor:
                payload["start_cursor"] = start_cursor
            
            try:
                response = requests.post(url, headers=self.headers, json=payload, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                results = data.get("results", [])
                
                for page in results:
                    paper = self.parse_paper(page)
                    if paper:
                        papers.append(paper)
                
                has_more = data.get("has_more", False)
                start_cursor = data.get("next_cursor")
                
            except requests.RequestException as e:
                print(f"Error fetching papers: {e}")
                sys.exit(1)
        
        return papers
    
    def parse_paper(self, page):
        """Parse a Notion page into paper data"""
        try:
            properties = page.get("properties", {})
            
            # Extract title
            title_prop = properties.get("Title", {})
            title = ""
            if title_prop.get("title"):
                title = "".join([text.get("plain_text", "") for text in title_prop["title"]])
            
            # Extract ArXiv ID
            arxiv_prop = properties.get("ArXiv ID", {})
            arxiv_id = ""
            if arxiv_prop.get("rich_text"):
                arxiv_id = "".join([text.get("plain_text", "") for text in arxiv_prop["rich_text"]])
            
            # Extract topic
            topic_prop = properties.get("Topic", {})
            topic = "General"
            if topic_prop.get("select") and topic_prop["select"]:
                topic = topic_prop["select"].get("name", "General")
            
            # Extract status
            status_prop = properties.get("Status", {})
            status = "To Read"  # Default status
            if status_prop.get("select") and status_prop["select"]:
                status = status_prop["select"].get("name", "To Read")
            
            # Extract summary
            summary_prop = properties.get("Summary", {})
            summary = ""
            if summary_prop.get("rich_text"):
                summary = "".join([text.get("plain_text", "") for text in summary_prop["rich_text"]])
            
            # Extract PDF URL
            pdf_prop = properties.get("PDF Url", {})
            pdf_url = ""
            if pdf_prop.get("url"):
                pdf_url = pdf_prop["url"]
            
            # Extract creation date
            created_prop = properties.get("Created", {})
            date = datetime.now().isoformat()
            if created_prop.get("date") and created_prop["date"].get("start"):
                date = created_prop["date"]["start"]
            
            # Extract authors from rich text field
            authors_prop = properties.get("Authors", {})
            authors = []
            if authors_prop.get("rich_text"):
                # Combine all text blocks
                authors_text = "".join([text.get("plain_text", "") for text in authors_prop["rich_text"]])
                if authors_text.strip():
                    # Split on common separators (comma or semicolon) and clean up
                    authors = [auth.strip() for auth in authors_text.replace(";", ",").split(",") if auth.strip()]
            
            # Fallback if no authors found
            if not authors:
                authors = ["Unknown Author"]
            
            # Extract and format summary with proper paragraphs
            summary_prop = properties.get("Summary", {})
            summary_parts = []
            if summary_prop.get("rich_text"):
                current_paragraph = []
                for text in summary_prop["rich_text"]:
                    content = text.get("plain_text", "")
                    annotations = text.get("annotations", {})
                    
                    # Handle line breaks
                    if content == "\n":
                        if current_paragraph:
                            summary_parts.append(" ".join(current_paragraph))
                            current_paragraph = []
                    else:
                        current_paragraph.append(content)
                
                # Add the last paragraph if any
                if current_paragraph:
                    summary_parts.append(" ".join(current_paragraph))
            
            summary = "\n\n".join(summary_parts) if summary_parts else "No summary available."
            
            # Skip papers without title
            if not title.strip():
                return None
            
            return {
                "id": page["id"],
                "title": title.strip(),
                "authors": authors,
                "summary": summary,
                "topic": topic,
                "status": status,
                "date": date,
                "arxiv_id": arxiv_id.strip(),
                "pdf_url": pdf_url.strip(),
                "notion_url": page.get("url", "")
            }
            
        except (KeyError, TypeError, ValueError) as e:
            print(f"Error parsing paper: {e}")
            return None
    
    def generate_papers_json(self, output_path="docs/papers.json"):
        """Generate papers.json file for the website"""
        print("Fetching papers from Notion...")
        papers = self.fetch_all_papers()
        
        if not papers:
            print("No papers found in Notion database")
            return False
        
        # Sort papers by date (newest first)
        papers.sort(key=lambda x: x["date"], reverse=True)
        
        # Generate metadata
        topics = list(set(paper["topic"] for paper in papers))
        metadata = {
            "generated_at": datetime.now().isoformat(),
            "total_papers": len(papers),
            "topics": sorted(topics),
            "last_updated": papers[0]["date"] if papers else datetime.now().isoformat()
        }
        
        # Create output structure
        output_data = {
            "metadata": metadata,
            "papers": papers
        }
        
        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Write JSON file
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            print(f"[SUCCESS] Generated {output_path}")
            print(f"   [INFO] {len(papers)} papers")
            print(f"   [INFO] {len(topics)} topics: {', '.join(topics)}")
            print(f"   [INFO] Last updated: {metadata['last_updated']}")
            
            return True
            
        except (IOError, OSError, UnicodeError) as e:
            print(f"[ERROR] Error writing JSON file: {e}")
            return False

def main():
    """Main function"""
    # Get environment variables
    notion_token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")
    
    if not notion_token:
        print("[ERROR] NOTION_TOKEN environment variable not set")
        sys.exit(1)
    
    if not database_id:
        print("[ERROR] NOTION_DATABASE_ID environment variable not set")
        sys.exit(1)
    
    # Initialize and run
    generator = NotionToWebsite(notion_token, database_id)
    
    success = generator.generate_papers_json()
    
    if not success:
        sys.exit(1)
    
    print("[SUCCESS] Website data generation complete!")

if __name__ == "__main__":
    main()