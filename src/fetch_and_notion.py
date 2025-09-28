import requests
import subprocess
import time
import os
import json
from datetime import datetime
from pathlib import Path
import warnings
from fetch import fetch_daily_papers
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

warnings.filterwarnings("ignore")

def format_authors(authors, max_authors=3):
    """Format author list with et al. if too many authors"""
    if not authors:
        return "Unknown Author"
    if len(authors) <= max_authors:
        return ", ".join(authors)
    return f"{', '.join(authors[:max_authors])} et al."

class NotionDatabase:
    def __init__(self, integration_token, database_id):
        """
        Initialize Notion database client
        
        Args:
            integration_token (str): Your Notion integration token
            database_id (str): Your 'Research Papers' data        print("\nProcessed papers:")
        for result in results:
            if result["success"]:
                action_text = "✅ Added" if result.get("action") == "added" else "⏭️ Skipped (exists)"
                print(f"  {action_text}: {result['title'][:50]}...") ID
        """
        self.token = integration_token
        self.database_id = database_id
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {integration_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
    
    def test_connection(self):
        """Test the Notion connection and get database schema"""
        url = f"{self.base_url}/databases/{self.database_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                db_info = response.json()
                print("✅ Notion connection successful!")
                print(f"Database title: {db_info.get('title', [{}])[0].get('text', {}).get('content', 'Unknown')}")
                
                # Show available properties
                properties = db_info.get('properties', {})
                print("Available properties:")
                for prop_name, prop_info in properties.items():
                    prop_type = prop_info.get('type', 'unknown')
                    print(f"  - {prop_name}: {prop_type}")
                
                return True, properties
            else:
                error_detail = ""
                try:
                    error_json = response.json()
                    error_detail = error_json.get("message", response.text)
                except json.JSONDecodeError:
                    error_detail = response.text
                
                print(f"❌ Connection failed: {response.status_code}")
                print(f"Error: {error_detail}")
                return False, None
                
        except requests.RequestException as e:
            print(f"❌ Connection error: {e}")
            return False, None
    
    def format_authors(self, authors):
        """Format author list with et al. if too many authors"""
        return format_authors(authors)
        
    def parse_markdown_to_rich_text(self, text):
        """Convert basic markdown to Notion rich text format"""
        if not text:
            return [{"text": {"content": "Analysis pending..."}}]
        
        # Simple markdown parsing for bold and italic
        rich_text = []
        current_text = ""
        i = 0
        
        while i < len(text):
            if i < len(text) - 1 and text[i:i+2] == "**":
                # Add current text if any
                if current_text:
                    rich_text.append({"text": {"content": current_text}})
                    current_text = ""
                
                # Find the closing **
                end = text.find("**", i + 2)
                if end != -1:
                    bold_text = text[i+2:end]
                    rich_text.append({
                        "text": {
                            "content": bold_text
                        },
                        "annotations": {
                            "bold": True
                        }
                    })
                    i = end + 2
                else:
                    current_text += text[i]
                    i += 1
            elif text[i] == "*" and i < len(text) - 1:
                # Add current text if any
                if current_text:
                    rich_text.append({"text": {"content": current_text}})
                    current_text = ""
                
                # Find the closing *
                end = text.find("*", i + 1)
                if end != -1:
                    italic_text = text[i+1:end]
                    rich_text.append({
                        "text": {
                            "content": italic_text
                        },
                        "annotations": {
                            "italic": True
                        }
                    })
                    i = end + 1
                else:
                    current_text += text[i]
                    i += 1
            else:
                current_text += text[i]
                i += 1
        
        # Add remaining text
        if current_text:
            rich_text.append({"text": {"content": current_text}})
        
        return rich_text if rich_text else [{"text": {"content": text[:2000]}}]
    
    def check_paper_exists(self, arxiv_id, title):
        """
        Check if a paper already exists in the database by ArXiv ID or title
        
        Args:
            arxiv_id (str): ArXiv ID of the paper
            title (str): Title of the paper
            
        Returns:
            tuple: (exists: bool, page_id: str or None)
        """
        if not arxiv_id and not title:
            return False, None
            
        url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
        
        # First try to find by ArXiv ID if available
        if arxiv_id:
            filter_data = {
                "filter": {
                    "property": "ArXiv ID",
                    "rich_text": {
                        "equals": arxiv_id
                    }
                }
            }
            
            try:
                response = requests.post(url, headers=self.headers, json=filter_data, timeout=30)
                if response.status_code == 200:
                    results = response.json().get('results', [])
                    if results:
                        return True, results[0]['id']
            except requests.RequestException:
                pass
        
        # If not found by ArXiv ID, try by title
        if title:
            filter_data = {
                "filter": {
                    "property": "Title",
                    "title": {
                        "equals": title[:2000]  # Notion title limit
                    }
                }
            }
            
            try:
                response = requests.post(url, headers=self.headers, json=filter_data, timeout=30)
                if response.status_code == 200:
                    results = response.json().get('results', [])
                    if results:
                        return True, results[0]['id']
            except requests.RequestException:
                pass
                
        return False, None
    
    def add_paper(self, paper_data):
        """
        Add a paper to the Notion database
        
        Args:
            paper_data (dict): Paper information
        """
        url = f"{self.base_url}/pages"
        
        # Ensure URLs are valid (Notion requires valid URLs or empty string)
        pdf_url = paper_data.get('pdf_url', '')
        if pdf_url and not pdf_url.startswith(('http://', 'https://')):
            pdf_url = ''
        
        # Create the page properties - focusing on what's important
        properties = {
            "Title": {
                "title": [
                    {
                        "text": {
                            "content": paper_data.get('title', 'Untitled')[:2000]
                        }
                    }
                ]
            },
            "Topic": {
                "select": {
                    "name": paper_data.get('topic', 'General')[:100]
                }
            },
            "ArXiv ID": {
                "rich_text": [
                    {
                        "text": {
                            "content": paper_data.get('arxiv_id', '')
                        }
                    }
                ]
            },
            "Summary": {
                "rich_text": self.parse_markdown_to_rich_text(paper_data.get('summary', 'Analysis pending...'))
            },
            "Status": {
                "select": {
                    "name": "To Read"  # Default status for new papers
                }
            },
            "Created": {
                "date": {
                    "start": datetime.now().isoformat()
                }
            },
            "Authors": {
                "rich_text": [
                    {
                        "text": {
                            "content": self.format_authors(paper_data.get('authors', ['Unknown Author']))
                        }
                    }
                ]
            }
        }
        
        # Only add PDF URL if it's valid
        if pdf_url:
            properties["PDF Url"] = {
                "url": pdf_url
            }
        
        data = {
            "parent": {"database_id": self.database_id},
            "properties": properties
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            if response.status_code == 200:
                page_data = response.json()
                return {
                    "success": True,
                    "page_id": page_data.get("id"),
                    "page_url": page_data.get("url"),
                    "message": "Paper added to Notion successfully",
                    "action": "added"
                }
            else:
                # Get detailed error information
                error_detail = ""
                try:
                    error_json = response.json()
                    error_detail = error_json.get("message", response.text)
                except json.JSONDecodeError:
                    error_detail = response.text
                
                print("Notion API Error Details:")
                print(f"Status Code: {response.status_code}")
                print(f"Response: {error_detail}")
                
                return {
                    "success": False,
                    "error": f"API Error: {response.status_code}",
                    "message": error_detail,
                    "response_text": response.text
                }
        except requests.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to add paper to Notion"
            }

def extract_arxiv_id(paper_url):
    """Extract arXiv ID from paper URL"""
    try:
        if '/abs/' in paper_url:
            return paper_url.split('/abs/')[-1]
        elif '/pdf/' in paper_url:
            return paper_url.split('/pdf/')[-1].replace('.pdf', '')
        else:
            return paper_url.split('/')[-1].replace('.pdf', '')
    except (IndexError, AttributeError):
        return None

def download_paper_pdf(paper, pdf_dir="./pdf"):
    """Download paper PDF from arXiv"""
    Path(pdf_dir).mkdir(exist_ok=True)
    
    arxiv_id = extract_arxiv_id(paper.get('pdf_url', paper.get('link', '')))
    
    if not arxiv_id:
        print("Could not extract arXiv ID from URLs")
        return None
    
    pdf_filename = f"{arxiv_id}.pdf"
    pdf_path = os.path.join(pdf_dir, pdf_filename)
    
    # Skip if already downloaded
    if os.path.exists(pdf_path):
        print(f"PDF already exists: {pdf_filename}")
        return pdf_path
    
    # Download from arXiv
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; ResearchBot/1.0)'}
        response = requests.get(pdf_url, headers=headers, stream=True, timeout=30)
        
        if response.status_code == 200:
            with open(pdf_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return pdf_path
        else:
            print(f"Failed to download PDF: HTTP {response.status_code}")
            return None
            
    except requests.RequestException as e:
        print(f"Error downloading PDF: {e}")
        return None

def analyze_paper_with_rag(pdf_path, cache_dir="./rag_cache"):
    """Use the doctor_paper tool to analyze the paper with caching"""
    # Create cache directory if it doesn't exist
    Path(cache_dir).mkdir(exist_ok=True)
    
    # Generate cache file name based on PDF name
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    cache_file = os.path.join(cache_dir, f"{pdf_name}_analysis.txt")
    
    # Check if analysis is already cached
    if os.path.exists(cache_file):
        print("   Using cached RAG analysis...")
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except (IOError, UnicodeDecodeError) as e:
            print(f"   Warning: Could not read cache file: {e}")
            # Continue with fresh analysis
    
    try:
        # Use the blog prompt for a good summary
        cmd = ["./doctor_paper", pdf_path]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            check=True
        )
        
        if result.returncode == 0:
            # Extract just the content between the separators
            output = result.stdout
            start_marker = "=" * 60
            
            analysis_result = None
            if start_marker in output:
                # Find content between the separators
                parts = output.split(start_marker)
                if len(parts) >= 3:
                    analysis_result = parts[1].strip()
                elif len(parts) == 2:
                    analysis_result = parts[1].strip()
            
            # Fallback: return the output after "Generating response..."
            if not analysis_result and "Generating response..." in output:
                analysis_result = output.split("Generating response...")[-1].strip()
            
            if not analysis_result:
                analysis_result = output
            
            # Cache the result for future use
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    f.write(analysis_result)
                print(f"   Analysis cached to: {cache_file}")
            except IOError as e:
                print(f"   Warning: Could not cache analysis: {e}")
            
            return analysis_result
        else:
            print(f"RAG analysis failed with return code: {result.returncode}")
            return None
            
    except subprocess.TimeoutExpired:
        print("RAG analysis timed out")
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error running RAG analysis: {e}")
        return None

def process_papers_to_notion(papers, notion_db, pdf_dir="./pdf"):
    """Process papers and add to Notion database"""
    results = []
    
    for i, paper in enumerate(papers, 1):
        print(f"\nProcessing paper {i}/{len(papers)}: {paper['title'][:50]}...")
        
        # Step 1: Check if paper already exists in Notion DB first
        arxiv_id = extract_arxiv_id(paper.get('pdf_url', paper.get('link', '')))
        print("   Checking if paper already exists in Notion database...")
        
        exists, existing_page_id = notion_db.check_paper_exists(arxiv_id, paper['title'])
        if exists:
            print("   Paper already exists in database - skipped!")
            results.append({
                "title": paper['title'],
                "success": True,
                "action": "skipped",
                "page_id": existing_page_id,
                "page_url": f"https://www.notion.so/{existing_page_id.replace('-', '')}"
            })
            continue
        
        print("   Paper is new - proceeding with processing...")
        
        # Step 2: Download PDF (only for new papers)
        print("   Downloading PDF...")
        pdf_path = download_paper_pdf(paper, pdf_dir)
        
        if not pdf_path:
            print("   Failed to download PDF")
            results.append({
                "title": paper['title'],
                "success": False,
                "error": "PDF download failed"
            })
            continue
        
        print(f"   PDF downloaded: {os.path.basename(pdf_path)}")
        
        # Step 3: Generate RAG summary (only for new papers)
        print("   Analyzing with RAG...")
        rag_summary = analyze_paper_with_rag(pdf_path)
        
        # Step 4: Prepare data for Notion
        notion_data = {
            "title": paper['title'],
            "authors": paper.get('authors', []),
            "topic": paper.get('topic', 'General'),
            "citation_count": paper.get('citation_count', 0),
            "pdf_url": paper.get('pdf_url', ''),
            "arxiv_id": arxiv_id or '',
            "summary": rag_summary
        }
        
        # Step 5: Add to Notion database
        print("   Adding to Notion database...")
        notion_result = notion_db.add_paper(notion_data)
        
        if notion_result["success"]:
            action = notion_result.get("action", "added")
            print("   Added to Notion successfully!")
            print(f"   Page ID: {notion_result.get('page_id', 'Unknown')}")
            results.append({
                "title": paper['title'],
                "success": True,
                "action": action,
                "page_id": notion_result.get('page_id', ''),
                "page_url": notion_result.get('page_url', '')
            })
        else:
            print(f"   Failed to add to Notion: {notion_result.get('error', 'Unknown error')}")
            results.append({
                "title": paper['title'],
                "success": False,
                "error": notion_result.get('error', 'Unknown error')
            })
        
        # Small delay to be nice to APIs and avoid rate limiting
        time.sleep(2)  # Add delay between API calls
    
    return results

def test_notion_connection():
    """Test Notion connection and database schema"""
    NOTION_TOKEN = os.getenv("NOTION_TOKEN")
    DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
    
    if not NOTION_TOKEN or not DATABASE_ID:
        print("❌ Missing NOTION_TOKEN or NOTION_DATABASE_ID in .env file")
        return False
    
    print("Testing Notion connection...")
    notion_db = NotionDatabase(NOTION_TOKEN, DATABASE_ID)
    success, properties = notion_db.test_connection()
    
    if success:
        print("\n✅ Connection test passed!")
        # Check for the fields we actually use
        required_props = ["Title", "Topic", "ArXiv ID", "PDF Url", "Summary", "Status"]
        missing_props = []
        
        for prop in required_props:
            if prop not in properties:
                missing_props.append(prop)
        
        if missing_props:
            print(f"⚠️  Missing properties in database: {', '.join(missing_props)}")
            print("Please add these properties to your Notion database:")
            for prop in missing_props:
                if prop == "PDF Url":
                    print(f"  - {prop}: URL")
                elif prop in ["Topic", "Status"]:
                    print(f"  - {prop}: Select")
                else:
                    print(f"  - {prop}: Text")
        else:
            print("✅ All required properties found!")
        return True
    else:
        print("❌ Connection test failed!")
        return False

def main():
    """Main pipeline function"""
    # Configuration - Load from environment variables
    NOTION_TOKEN = os.getenv("NOTION_TOKEN")
    DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
    PDF_DIR = os.getenv("PDF_DIR", "./pdf")  # Default to ./pdf if not set
    
    # Validate required environment variables
    if not NOTION_TOKEN:
        print("Error: NOTION_TOKEN not found in environment variables")
        print("Please add NOTION_TOKEN=your_token to your .env file")
        return
    
    if not DATABASE_ID:
        print("Error: NOTION_DATABASE_ID not found in environment variables")
        print("Please add NOTION_DATABASE_ID=your_database_id to your .env file")
        return
    
    # Test connection first
    print("Testing Notion connection first...")
    if not test_notion_connection():
        print("Please fix the connection issues before proceeding.")
        return
    
    print("\nStarting Paper-to-Notion Pipeline")
    print("=" * 50)
    print("Optimizations enabled:")
    print("  - Check Notion DB first (skip processing if paper exists)")
    print("  - PDF download caching")
    print("  - RAG analysis caching")
    print("=" * 50)
    
    # Check if RAG script exists
    if not os.path.exists("doctor_paper"):
        print("Error: doctor_paper script not found in current directory")
        return
    
    # Step 1: Initialize Notion client
    notion_db = NotionDatabase(NOTION_TOKEN, DATABASE_ID)
    
    # Step 2: Create PDF directory
    Path(PDF_DIR).mkdir(exist_ok=True)
    print(f"PDF directory: {PDF_DIR}")
    
    # Step 3: Fetch papers
    print("Fetching papers...")
    papers = fetch_daily_papers()
    print(f"Found {len(papers)} papers")
    
    # Step 4: Process papers
    print("\nProcessing papers...")
    results = process_papers_to_notion(papers, notion_db, PDF_DIR)
    
    # Step 5: Print results
    print("\n" + "=" * 50)
    print("RESULTS")
    print("=" * 50)
    
    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful
    added = sum(1 for r in results if r.get("success") and r.get("action") == "added")
    skipped = sum(1 for r in results if r.get("success") and r.get("action") == "skipped")
    
    print(f"Total processed: {len(results)} papers")
    print(f"Added: {added}")
    print(f"Skipped (already exists): {skipped}")
    print(f"Failed: {failed}")
    
    if successful > 0:
        print("\nProcessed papers:")
        for result in results:
            if result["success"]:
                print(f"   - {result['title'][:60]}...")
    
    print(f"\nPDFs stored in: {os.path.abspath(PDF_DIR)}")
    print("Check your Notion database for the new entries!")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Just test the connection
        test_notion_connection()
    else:
        # Run the full pipeline
        main()