import instaloader
import pandas as pd
import sys
import json
from datetime import datetime, timedelta
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def load_config(config_path):
    with open(config_path, 'r') as f:
        return json.load(f)

def fetch_posts(handles, days_back):
    L = instaloader.Instaloader(download_pictures=False, download_videos=False,
                                download_comments=False, save_metadata=False, compress_json=False)
    data = []
    since = datetime.now() - timedelta(days=days_back)

    for handle in handles:
        try:
            profile = instaloader.Profile.from_username(L.context, handle)
            for post in profile.get_posts():
                if post.date_local >= since:
                    data.append({
                        "handle": handle,
                        "date": post.date_local.strftime("%Y-%m-%d"),
                        "caption": post.caption[:200] if post.caption else "",
                        "likes": post.likes,
                        "comments": post.comments,
                        "url": f"https://www.instagram.com/p/{post.shortcode}/"
                    })
        except Exception as e:
            print(f"Error fetching {handle}: {e}")
    return pd.DataFrame(data)

def write_to_sheets(df, config):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(config["google_sheets"]["service_account_json_path"], scope)
    client = gspread.authorize(creds)
    sheet = client.open(config["google_sheets"]["sheet_name"])

    # Write raw posts
    raw_tab = sheet.worksheet(config["google_sheets"]["posts_raw_tab"])
    raw_tab.clear()
    raw_tab.update([df.columns.values.tolist()] + df.values.tolist())

if __name__ == "__main__":
    config = load_config("config.json")
    with open(sys.argv[2], 'r') as f:
        handles = [line.strip() for line in f if line.strip()]
    df = fetch_posts(handles, config["days_back"])
    if not df.empty:
        write_to_sheets(df, config)
        df.to_csv("posts_raw.csv", index=False)
    else:
        print("No posts found.")
