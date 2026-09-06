#!/usr/bin/env python3
"""
Dr. Paper: Telegram Editorial Review Bot
Sends candidate research cards to Telegram with 1-click [Publish], [Feature], [Reject] inline buttons.
Minimalist formatting with zero emojis and quiet typography.
"""

import html
import json
import os
import sys
import time
from typing import Dict, List, Optional
import requests

from config import config
from db import db

TELEGRAM_API_BASE = "https://api.telegram.org/bot"

def is_telegram_configured() -> bool:
    """Check if Telegram Bot Token and Chat ID are configured"""
    return bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)

def send_telegram_message(text: str, reply_markup: Optional[Dict] = None, chat_id: Optional[str] = None) -> Optional[Dict]:
    """Send a message via Telegram Bot API (HTML formatted)"""
    if not config.TELEGRAM_BOT_TOKEN:
        print("[WARN] TELEGRAM_BOT_TOKEN is not configured.")
        return None

    target_chat = chat_id or config.TELEGRAM_CHAT_ID
    if not target_chat:
        print("[WARN] TELEGRAM_CHAT_ID is not configured.")
        return None

    url = f"{TELEGRAM_API_BASE}{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": target_chat,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"[ERROR] Telegram API error ({response.status_code}): {response.text}")
            return None
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")
        return None

def format_paper_card_html(paper: Dict) -> str:
    """Format a research paper draft into clean, quiet Telegram HTML"""
    title = html.escape(paper.get("title", "Untitled Paper"))
    arxiv_id = paper.get("arxiv_id", "")
    score = paper.get("score", 0.0)
    source = html.escape(paper.get("curated_source", "arxiv"))
    edition = html.escape(paper.get("published_edition", ""))
    
    analysis = paper.get("structured_analysis", {})
    gist = analysis.get("plain_english_gist") or analysis.get("one_line_hook") or analysis.get("problem", "")
    takeaways = analysis.get("key_takeaways", [])

    arxiv_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""
    title_link = f'<a href="{arxiv_url}"><b>{title}</b></a>' if arxiv_url else f'<b>{title}</b>'

    lines = [
        title_link,
        f"<i>Score: {score:.1f} · {source} · {edition}</i>",
        ""
    ]

    if gist:
        lines.extend([
            "<b>The Gist</b>",
            html.escape(gist),
            ""
        ])

    if takeaways:
        lines.append("<b>Key Takeaways</b>")
        for t in takeaways[:4]:
            lines.append(f"• {html.escape(t)}")
        lines.append("")

    return "\n".join(lines).strip()

def build_review_inline_keyboard(arxiv_id: str) -> Dict:
    """Build minimalist 1-click URL buttons that update Supabase serverlessly without background listeners"""
    base_url = f"{config.SUPABASE_URL}/functions/v1/moderate"
    token_param = f"&token={config.MODERATION_TOKEN}" if config.MODERATION_TOKEN else ""
    apikey_param = f"&apikey={config.SUPABASE_ANON_KEY}" if config.SUPABASE_ANON_KEY else ""
    
    pub_url = f"{base_url}?id={arxiv_id}&action=pub{token_param}{apikey_param}"
    feat_url = f"{base_url}?id={arxiv_id}&action=feat{token_param}{apikey_param}"
    rej_url = f"{base_url}?id={arxiv_id}&action=rej{token_param}{apikey_param}"
    arxiv_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "https://arxiv.org"

    return {
        "inline_keyboard": [
            [
                {"text": "Publish", "url": pub_url},
                {"text": "Feature", "url": feat_url},
                {"text": "Reject", "url": rej_url}
            ],
            [
                {"text": "arXiv", "url": arxiv_url}
            ]
        ]
    }

def send_paper_review_card(paper: Dict, chat_id: Optional[str] = None) -> bool:
    """Send a single interactive research review card to Telegram"""
    arxiv_id = paper.get("arxiv_id", "")
    text = format_paper_card_html(paper)
    keyboard = build_review_inline_keyboard(arxiv_id) if arxiv_id else None
    res = send_telegram_message(text=text, reply_markup=keyboard, chat_id=chat_id)
    return res is not None and res.get("ok", False)

def notify_new_drafts(papers: List[Dict], chat_id: Optional[str] = None) -> int:
    """Send review cards for a list of newly ingested drafts"""
    if not is_telegram_configured():
        return 0

    sent_count = 0
    for p in papers:
        if send_paper_review_card(p, chat_id=chat_id):
            sent_count += 1
            time.sleep(0.5)  # Telegram rate limit safety
    return sent_count

def answer_callback_query(callback_query_id: str, text: str):
    """Acknowledge Telegram callback query"""
    url = f"{TELEGRAM_API_BASE}{config.TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    try:
        requests.post(url, json={"callback_query_id": callback_query_id, "text": text}, timeout=5)
    except Exception as e:
        print(f"[WARN] Failed to answer callback query: {e}")

def edit_message_text(chat_id: int, message_id: int, text: str, reply_markup: Optional[Dict] = None):
    """Edit message text and buttons after moderation action is taken"""
    url = f"{TELEGRAM_API_BASE}{config.TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[WARN] Failed to edit message text: {e}")

def handle_callback_action(callback: Dict) -> bool:
    """Process button click from Telegram"""
    callback_id = callback.get("id")
    data = callback.get("data", "")
    message = callback.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")
    original_text = message.get("text", "")

    if ":" not in data:
        answer_callback_query(callback_id, "Unknown action")
        return False

    action, arxiv_id = data.split(":", 1)
    
    if action == "pub":
        success = db.update_paper_editorial(arxiv_id, status="published")
        if success:
            answer_callback_query(callback_id, f"Published {arxiv_id}")
            status_banner = f"\n\n<b>[Published]</b>"
            new_kb = {"inline_keyboard": [[{"text": "arXiv", "url": f"https://arxiv.org/abs/{arxiv_id}"}]]}
            edit_message_text(chat_id, message_id, html.escape(original_text) + status_banner, reply_markup=new_kb)
            print(f"[TELEGRAM] Published {arxiv_id}")
            return True
        else:
            answer_callback_query(callback_id, f"Error publishing {arxiv_id}")
            return False

    elif action == "feat":
        success = db.update_paper_editorial(arxiv_id, status="published", is_featured=True)
        if success:
            answer_callback_query(callback_id, f"Featured {arxiv_id}")
            status_banner = f"\n\n<b>[Featured & Published]</b>"
            new_kb = {"inline_keyboard": [[{"text": "arXiv", "url": f"https://arxiv.org/abs/{arxiv_id}"}]]}
            edit_message_text(chat_id, message_id, html.escape(original_text) + status_banner, reply_markup=new_kb)
            print(f"[TELEGRAM] Featured {arxiv_id}")
            return True
        else:
            answer_callback_query(callback_id, f"Error featuring {arxiv_id}")
            return False

    elif action == "rej":
        success = db.update_paper_editorial(arxiv_id, status="rejected")
        if success:
            answer_callback_query(callback_id, f"Rejected {arxiv_id}")
            status_banner = f"\n\n<b>[Rejected]</b>"
            edit_message_text(chat_id, message_id, html.escape(original_text) + status_banner, reply_markup={"inline_keyboard": []})
            print(f"[TELEGRAM] Rejected {arxiv_id}")
            return True
        else:
            answer_callback_query(callback_id, f"Error rejecting {arxiv_id}")
            return False

    return False

def listen_loop():
    """Poll Telegram updates and process inline button callbacks in real-time"""
    if not config.TELEGRAM_BOT_TOKEN:
        print("[ERROR] TELEGRAM_BOT_TOKEN is not set in environment or .env")
        sys.exit(1)

    print("=" * 70)
    print("Dr. Paper: Telegram Review Listener Active")
    print("Waiting for moderation actions [Publish / Feature / Reject]...")
    print("Press Ctrl+C to stop.")
    print("=" * 70)

    offset = None
    url = f"{TELEGRAM_API_BASE}{config.TELEGRAM_BOT_TOKEN}/getUpdates"

    while True:
        try:
            params = {"timeout": 20}
            if offset:
                params["offset"] = offset

            resp = requests.get(url, params=params, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    if "callback_query" in update:
                        handle_callback_action(update["callback_query"])
            time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n[!] Listener stopped.")
            break
        except Exception as e:
            print(f"[WARN] Error in polling loop: {e}")
            time.sleep(3)

def send_test_card():
    """Send a test card for a real paper in Supabase to verify bot and serverless moderation"""
    if not is_telegram_configured():
        print("[ERROR] Please configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env first.")
        return False

    # Try to pick a real paper from Supabase
    test_paper = None
    if db.is_configured():
        try:
            resp = requests.get(f"{db.rest_url}/papers?select=*&limit=1", headers=db.headers, timeout=5)
            if resp.status_code == 200 and resp.json():
                test_paper = resp.json()[0]
        except Exception:
            pass

    if not test_paper:
        test_paper = {
            "arxiv_id": "2609.03153",
            "title": "VeriPhy: Agentic Physical Reasoning for World Model Evaluation and Refinement",
            "score": 14.5,
            "curated_source": "Hugging Face Daily Papers",
            "published_edition": "Edition 2026-W36",
            "structured_analysis": {
                "plain_english_gist": "VeriPhy introduces deterministic verification steps for physical reasoning in multimodal world models.",
                "key_takeaways": [
                    "Eliminates hallucinated physics by 64% in simulated benchmarks.",
                    "Integrates with existing vision-language architectures without retraining."
                ]
            }
        }

    print(f"[*] Sending test card for '{test_paper.get('title')}' (arXiv: {test_paper.get('arxiv_id')}) to Telegram chat {config.TELEGRAM_CHAT_ID}...")
    success = send_paper_review_card(test_paper)
    if success:
        print("[+] Test card sent successfully. Check your Telegram app.")
    else:
        print("[!] Failed to send test card. Please check your token and chat ID.")
    return success

def notify_all_staged_drafts():
    """Fetch all pending drafts from Supabase and send review cards to Telegram"""
    if not db.is_configured() or not is_telegram_configured():
        print("[ERROR] Ensure Supabase and Telegram are configured.")
        return

    drafts = db.get_pending_drafts(limit=15)
    if not drafts:
        print("[+] No pending drafts in database.")
        return

    print(f"[*] Sending {len(drafts)} draft review cards to Telegram...")
    sent = notify_new_drafts(drafts)
    print(f"[+] Sent {sent}/{len(drafts)} cards to Telegram.")

def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ("--test", "-t"):
            send_test_card()
        elif arg in ("--listen", "-l"):
            listen_loop()
        elif arg in ("--notify-drafts", "-n"):
            notify_all_staged_drafts()
        else:
            print("Usage: python src/telegram_bot.py [--test | --listen | --notify-drafts]")
    else:
        send_test_card()

if __name__ == "__main__":
    main()
