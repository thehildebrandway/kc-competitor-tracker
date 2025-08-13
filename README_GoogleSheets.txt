# KC Competitor Tracker

## How this works
- Runs every Monday via GitHub Actions
- Pulls last 30 days of posts from `competitors.csv`
- Writes to Google Sheet (`posts_raw` tab)
- Use `summary_prompt_template.txt` with ChatGPT to make your weekly brief

## Setup Steps
1. Share Google Sheet with service account email.
2. Add secrets in repo settings (see run.yml comments).
3. Adjust cron schedule in run.yml if needed.
