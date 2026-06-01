#!/usr/bin/env python3
"""
Termux Deep-Description Mass Hunter
Extracts full metadata including descriptions for high-volume sweeps.
"""

import re
import json
import time
import subprocess
import argparse
from datetime import datetime

# ANSI colors
C_RESET   = "\033[0m"
C_BOLD    = "\033[1m"
C_RED     = "\033[91m"
C_GREEN   = "\033[92m"
C_YELLOW  = "\033[93m"
C_CYAN    = "\033[96m"

def deep_scan(args):
    # Constructing a targeted search string sorted by upload date
    search_url = f"ytsearchdate{args.max_results}:{args.query}"
    print(f"{C_CYAN}[*] Initializing Deep Crawler... Target: Up to {args.max_results} videos.{C_RESET}")
    print(f"{C_CYAN}[*] Filtering ceiling: Videos must have ≤ {args.max_views} views.{C_RESET}")
    print(f"{C_YELLOW}[!] Pacing delay active to protect your IP address from blocks.{C_RESET}\n")

    # Standard execution command (No flat-playlist, we need full text data)
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-playlist",
        "--ignore-errors",
        search_url
    ]

    key_regex = re.compile(args.pattern, re.IGNORECASE)
    video_counter = 0
    found_keys = 0

    try:
        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1
        ) as proc:

            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                video_counter += 1
                
                title = data.get("title", "Unknown Title")
                description = data.get("description", "") or ""
                url = data.get("webpage_url", "")
                
                # Fetch views safely
                view_count = data.get("view_count")
                view_count = int(view_count) if view_count is not None else 0

                # Print progress update for every single video evaluated
                title_short = title[:40] + ('...' if len(title) > 40 else '')
                print(f"[{video_counter}] Auditing: '{title_short}' | Views: {view_count}")

                # View ceiling threshold filter
                if view_count > args.max_views:
                    continue

                # Audit full description text block and title string
                text_to_scan = f"{title}\n{description}"
                found = key_regex.findall(text_to_scan)

                if found:
                    unique_keys = set(found)
                    found_keys += len(unique_keys)
                    print(f"\n{C_GREEN}{C_BOLD}" + "=" * 50)
                    print("[+] MATCH DETECTED IN DESCRIPTION CODES")
                    print(f"Title : {title}")
                    print(f"URL   : {url}")
                    print("-" * 50)
                    for key in unique_keys:
                        print(f">>> RAW CODE LOCATED: {C_YELLOW}{key}{C_GREEN}")
                    print("=" * 50 + f"\n{C_RESET}")

                    with open(args.key_log, "a") as f:
                        for key in unique_keys:
                            f.write(f"{key}\t{url}\t{datetime.now().isoformat()}\n")

                # Small anti-ban rest interval between processing individual video links
                time.sleep(args.delay)

            proc.wait()

    except FileNotFoundError:
        print(f"{C_RED}[-] Error: 'yt-dlp' missing from system configuration.{C_RESET}")
    except Exception as e:
        print(f"{C_RED}[-] System Exception: {e}{C_RESET}")

    print(f"\n{C_CYAN}[*] Sweep Finished. Processed: {video_counter} videos. Total Keys Saved: {found_keys}{C_RESET}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deep Search Scraper")
    parser.add_argument("query", help="Search string input target")
    parser.add_argument("-m", "--max-results", type=int, default=100, help="Adjust total processing depth limit")
    parser.add_argument("--max-views", type=int, default=3, help="Strict view ceiling")
    parser.add_argument("-d", "--delay", type=float, default=0.5, help="Seconds to sleep between items")
    parser.add_argument("-p", "--pattern", default=r'\b[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}\b')
    parser.add_argument("-l", "--key-log", default="hunter_log.txt")
    
    args = parser.parse_args()
    deep_scan(args)
