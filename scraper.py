import os, time, datetime as dt
import pandas as pd
import instaloader
from urllib.parse import unquote
from datetime import timezone, datetime, timedelta
from pathlib import Path

# --- Config ---
COMPETITORS = [
    "fareisle",
    "wildnutritionist",
    "daniellehartruns",
    "absbyamy",
    "emilyxlevi",
    "brian_pruett",
]
DAYS_BACK = int(os.getenv("DAYS_BACK", "30"))

# Read cookie from Actions secret
RAW_SESSIONID = os.getenv("IG_SESSIONID", "").strip()
if not RAW_SESSIONID:
    raise SystemExit("Missing IG_SESSIONID secret")

# --- Instaloader session ---
L = instaloader.Instaloader(
    download_pictures=False,
    download_videos=False,
    download_video_thumbnails=False,
    download_geotags=False,
    download_comments=False,
    save_metadata=False,
    compress_json=False,
    max_connection_attempts=3
)

# Clear any stale cookie
for c in list(L.context._session.cookies):
    if c.name.lower() == "sessionid":
        try:
            L.context._session.cookies.clear(domain=c.domain, path=c.path, name=c.name)
        except Exception:
            pass

# Attach cookie for both domains
IG_SESSIONID = unquote(RAW_SESSIONID.strip().strip('"').strip("'"))
for dom in ["instagram.com", ".instagram.com"]:
    L.context._session.cookies.set("sessionid", IG_SESSIONID, domain=dom, path="/")

# Quick cookie sanity check (200 means valid, 302 redirect means invalid)
r = L.context._session.get("https://www.instagram.com/accounts/edit/", allow_redirects=False)
print("Auth check HTTP:", r.status_code)
if r.status_code == 302:
    raise SystemExit("Cookie invalid/expired. Update IG_SESSIONID secret.")

since = datetime.utcnow() - timedelta(days=DAYS_BACK)

def to_iso_utc(ts):
    try:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return ""

rows = []
MAX_POSTS_PER_PROFILE = 120  # scan cap for speed

for u in COMPETITORS:
    try:
        p = instaloader.Profile.from_username(L.context, u)
        scanned = kept = 0
        for post in p.get_posts():
            scanned += 1
            d_utc = post.date_utc
            d_cmp = d_utc.astimezone(timezone.utc).replace(tzinfo=None) if d_utc.tzinfo else d_utc
            if d_cmp >= since:
                cap = (post.caption or "").replace("\n"," ").strip()
                hook10 = " ".join(cap.split()[:10])

                if post.is_video:
                    ptype = "reel"
                elif post.typename == "GraphSidecar":
                    ptype = "carousel"
                else:
                    ptype = "image"

                # Best-effort counts (may be 0 if IG hides them)
                likes_count = getattr(post, "likes", None) or getattr(post, "likes_count", None) or 0
                comments_count = getattr(post, "comments", None) or getattr(post, "comments_count", None) or 0
                followers = p.followers if p else 0
                er = round(((likes_count + comments_count) / followers) * 100, 2) if followers else ""

                rows.append({
                    "platform": "instagram",
                    "profile": f"@{u}",
                    "post_url": f"https://www.instagram.com/p/{post.shortcode}/",
                    "published_at": to_iso_utc(d_utc),
                    "type": ptype,
                    "caption": cap[:500],
                    "hook_text": hook10,
                    "likes": likes_count,
                    "comments": comments_count,
                    "followers_snapshot": followers,
                    "est_engagement_rate": er
                })
                kept += 1

            if scanned >= MAX_POSTS_PER_PROFILE:
                break

        print(f"@{u}: scanned {scanned}, kept {kept}")
        time.sleep(2)

    except Exception as e:
        print(f"@{u}: ERROR -> {e}")
        time.sleep(5)

df = pd.DataFrame(rows, columns=[
    "platform","profile","post_url","published_at","type","caption","hook_text",
    "likes","comments","followers_snapshot","est_engagement_rate"
])
if not df.empty and df["published_at"].fillna("").ne("").any():
    df = df.sort_values("published_at", ascending=False, na_position="last")

# Ensure folder and write CSV
out_dir = Path("data"); out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / "posts_raw.csv"
df.to_csv(out_path, index=False, encoding="utf-8")
print(f"✅ Wrote {len(df)} rows → {out_path}")
