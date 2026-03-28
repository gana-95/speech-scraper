# 🏛️ Lok Sabha Debate Scraper

An automated pipeline that scrapes English debate PDFs from the [Lok Sabha Digital Library](https://eparlib.sansad.in/handle/123456789/2963706), organises them by year, and pushes them nightly to a public storage repository — making Indian parliamentary speech data freely accessible for research and analysis.

📦 **Storage repo:** [gana-95/parliament-pdfs](https://github.com/gana-95/parliament-pdfs)

---

## How It Works

```
Every hour  (cron)      →  scraper.py --limit 10   →  debates/YEAR/*.pdf
Every midnight (cron)   →  upload_to_github.sh      →  gana-95/parliament-pdfs
Git push to main        →  GitHub Actions           →  GCP VM (auto-deploy)
```

The scraper maintains pagination state across runs, so it picks up exactly where it left off each hour. The nightly upload script commits any newly downloaded PDFs to the storage repository with a dated commit message.

---

## Repository Structure

```
speech-scraper/
├── .github/
│   └── workflows/
│       └── deploy.yml          # CD: auto-deploys to GCP VM on push
├── scripts/
│   └── upload_to_github.sh     # Nightly PDF push to storage repo
├── src/
│   ├── __init__.py
│   ├── scraper.py              # Core scraper logic
│   └── state.py               # Pagination state manager
├── debates/                    # Downloaded PDFs — gitignored
│   ├── 2023/
│   ├── 2024/
│   └── 2025/
├── logs/                       # Cron logs — gitignored
├── .env.example
├── requirements.txt
├── setup.sh                    # One-time GCP VM setup script
└── README.md
```

---

## Quick Start (Local)

```bash
git clone https://github.com/gana-95/speech-scraper.git
cd speech-scraper

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Fill in your values (see Environment Variables below)
```

### Run the scraper

```bash
# Fetch the latest 10 debate PDFs
python -m src.scraper --limit 10

# Fetch all debates from a specific year
python -m src.scraper --start-date 01-Jan-2025 --end-date 31-Dec-2025

# Reset pagination state and start from the beginning
python -m src.scraper --reset --limit 10
```

---

## Scraper Arguments

| Argument | Default | Description |
|---|---|---|
| `--limit N` | unlimited | Max PDFs to download per run |
| `--start-date` | none | Only debates on or after this date (DD-Mon-YYYY) |
| `--end-date` | none | Only debates on or before this date (DD-Mon-YYYY) |
| `--output-dir` | `debates` | Base output folder (year subfolders are auto-created) |
| `--reset` | false | Reset pagination state and restart from the beginning |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
GITHUB_TOKEN=your_pat_here          # Personal access token with repo write access
STORAGE_REPO=gana-95/parliament-pdfs
GIT_USER_NAME=your-github-username
GIT_USER_EMAIL=your@email.com
```

---

## GCP VM Setup

The application runs on a GCP VM with two cron jobs. Use the provided setup script for a one-time configuration:

```bash
bash setup.sh
```

### Cron Schedule

```cron
# Fetch 10 new PDFs every hour
0 * * * * cd /opt/speech-scraper && .venv/bin/python -m src.scraper --limit 10 >> logs/scraper.log 2>&1

# Push new PDFs to storage repo every midnight
0 0 * * * cd /opt/speech-scraper && bash scripts/upload_to_github.sh >> logs/upload.log 2>&1
```

---

## Continuous Deployment

Pushing to `main` triggers a GitHub Actions workflow (`.github/workflows/deploy.yml`) that SSHs into the GCP VM and pulls the latest code automatically — no manual deployment needed.

### Required GitHub Secrets

| Secret | Description |
|---|---|
| `GCP_VM_HOST` | External IP address of the GCP VM |
| `GCP_VM_USER` | SSH username (e.g. `ubuntu`) |
| `GCP_VM_PRIVATE_KEY` | Private SSH key for VM access |

---

## Data Source

Debate PDFs are sourced from the [Sansad Digital Library](https://eparlib.sansad.in/handle/123456789/2963706), the official open-access archive of Lok Sabha proceedings. All data is in the public domain.

---

## License

For academic and research use.
