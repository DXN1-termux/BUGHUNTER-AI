import re
import subprocess
import json
import concurrent.futures
import multiprocessing
from datetime import datetime, timedelta

# Config
KEY_PATTERN = re.compile(r"\bBO7\b", re.IGNORECASE)  # Case-insensitive match
MAX_VIDEOS = 100  # Limit to avoid excessive requests
DAYS_OLD = 7  # Only check videos uploaded in the last 7 days
NUM_CORES = multiprocessing.cpu_count()  # Use all CPU cores

def get_recent_videos():
    # Use yt-dlp to fetch recent videos (sorted by upload date)
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(id)s|%(title)s|%(upload_date)s|%(view_count)s|%(description)s",
        "--dateafter", (datetime.now() - timedelta(days=DAYS_OLD)).strftime("%Y%m%d"),
        "--max-downloads", str(MAX_VIDEOS),
        "ytsearchdate:all"  # Search for recent videos
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip().split("\n")

def process_video(video_str):
    try:
        video_id, title, upload_date, views, description = video_str.split("|", 4)
        views = int(views)
        if views <= 1 and KEY_PATTERN.search(description):
            return {
                "id": video_id,
                "title": title,
                "views": views,
                "upload_date": upload_date,
                "description": description,
                "url": f"https://youtu.be/{video_id}"
            }
    except Exception as e:
        print(f"Error processing video: {e}")
    return None

def main():
    print(f"Fetching recent videos (last {DAYS_OLD} days)...")
    video_strings = get_recent_videos()
    results = []

    with concurrent.futures.ProcessPoolExecutor(max_workers=NUM_CORES) as executor:
        futures = [executor.submit(process_video, vs) for vs in video_strings]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    print(f"\nFound {len(results)} videos with 0/1 views and 'BO7' in description:")
    for result in results:
        print(f"\nTitle: {result['title']}")
        print(f"Views: {result['views']}")
        print(f"Upload Date: {result['upload_date']}")
        print(f"URL: {result['url']}")
        print(f"Description: {result['description'][:200]}...")

if __name__ == "__main__":
    main()
