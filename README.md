# Speech Scraper

Automated pipeline to download Lok Sabha Debate PDFs (English) from the
[Speech Digital Library](https://eparlib.sansad.in/handle/123456789/2963706),
organised by year, and pushed daily to a storage GitHub repository.

---

## Architecture

```
Every hour  (cron) → scraper.py --limit 10  → debates/YEAR/*.pdf
Every midnight (cron) → upload_to_github.sh → Speech-pdfs repo
Git push to main  → GitHub Actions          → GCP VM git pull
```

---

## Directory Structure

```
speech-scraper/
├── .github/workflows/deploy.yml   # Auto-deploy on git push
├── scripts/
│   └── upload_to_github.sh        # Daily PDF upload to storage repo
├── src/
│   ├── __init__.py
│   ├── scraper.py                 # Main scraper
│   └── state.py                  # Pagination state manager
├── debates/                       # Downloaded PDFs (gitignored)
│   ├── 2023/
│   ├── 2024/
│   └── 2025/
├── logs/                          # Cron logs (gitignored)
├── .env.example                   # Environment variable template
├── .gitignore
├── requirements.txt
├── setup.sh                       # One-time VM setup
└── README.md
```

---

## Quick Start (Local)

```bash
git clone https://github.com/gana-95/speech-scraper.git
cd Speech-scraper

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your values

# Fetch latest 10 debates
python -m src.scraper --limit 10

# Fetch all 2025 debates
python -m src.scraper --start-date 01-Jan-2025 --end-date 31-Dec-2025

# Reset state and start over
python -m src.scraper --reset --limit 10
```

---

## GCP VM Setup

See the full GCP setup guide below, or run:

```bash
bash setup.sh
```

---

## Scraper Arguments

| Argument | Default | Description |
|---|---|---|
| `--limit N` | unlimited | Max PDFs to download this run |
| `--start-date` | none | Only debates on or after this date |
| `--end-date` | none | Only debates on or before this date |
| `--output-dir` | `debates` | Base folder (year subfolders auto-created) |
| `--reset` | false | Reset pagination state to beginning |

---

## Cron Schedule

```cron
# Every hour: fetch 10 new PDFs
0 * * * * cd /opt/speech-scraper && .venv/bin/python -m src.scraper --limit 10 >> logs/scraper.log 2>&1

# Every midnight: push new PDFs to storage repo
0 0 * * * cd /opt/speech-scraper && bash scripts/upload_to_github.sh >> logs/upload.log 2>&1
```

---

## GitHub Secrets Required

| Secret | Description |
|---|---|
| `GCP_VM_HOST` | External IP of GCP VM |
| `GCP_VM_USER` | SSH username (e.g. `ubuntu`) |
| `GCP_SSH_PRIVATE_KEY` | Private SSH key for the VM |

---

## License

For academic and research use.