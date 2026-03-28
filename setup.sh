#!/bin/bash
# setup.sh
# --------
# One-time setup script to run on the GCP VM after cloning the repo.
# Run as: bash setup.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================================"
echo "  Parliament Scraper -- VM Setup"
echo "============================================================"

# ── System packages ─────────────────────────────────────────────────────────
echo "[1/5] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y python3 python3-pip python3-venv git rsync cron

# ── Python virtual environment ───────────────────────────────────────────────
echo "[2/5] Creating Python virtual environment..."
python3 -m venv "$PROJECT_DIR/.venv"
source "$PROJECT_DIR/.venv/bin/activate"
pip install --upgrade pip --quiet
pip install -r "$PROJECT_DIR/requirements.txt" --quiet
echo "      venv ready at $PROJECT_DIR/.venv"

# ── Directories ──────────────────────────────────────────────────────────────
echo "[3/5] Creating required directories..."
mkdir -p "$PROJECT_DIR/debates"
mkdir -p "$PROJECT_DIR/logs"
mkdir -p /opt/parliament-pdfs

# ── .env file ────────────────────────────────────────────────────────────────
echo "[4/5] Setting up .env..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "      IMPORTANT: Edit $PROJECT_DIR/.env with your actual values."
else
    echo "      .env already exists, skipping."
fi

# ── Script permissions ───────────────────────────────────────────────────────
chmod +x "$PROJECT_DIR/scripts/upload_to_github.sh"

# ── Cron jobs ────────────────────────────────────────────────────────────────
echo "[5/5] Installing cron jobs..."

VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
CRON_SCRAPER="0 * * * * cd $PROJECT_DIR && $VENV_PYTHON -m src.scraper --limit 10 >> $PROJECT_DIR/logs/scraper.log 2>&1"
CRON_UPLOAD="0 0 * * * cd $PROJECT_DIR && bash $PROJECT_DIR/scripts/upload_to_github.sh >> $PROJECT_DIR/logs/upload.log 2>&1"

# Add crons only if not already present
( crontab -l 2>/dev/null | grep -qF "src.scraper" ) \
    && echo "      Scraper cron already exists, skipping." \
    || ( crontab -l 2>/dev/null; echo "$CRON_SCRAPER" ) | crontab -

( crontab -l 2>/dev/null | grep -qF "upload_to_github" ) \
    && echo "      Upload cron already exists, skipping." \
    || ( crontab -l 2>/dev/null; echo "$CRON_UPLOAD" ) | crontab -

echo ""
echo "============================================================"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Edit .env with your GITHUB_TOKEN and PDF_STORAGE_REPO"
echo "  2. Verify crons: crontab -l"
echo "  3. Test scraper: $VENV_PYTHON -m src.scraper --limit 2"
echo "  4. Test upload:  bash scripts/upload_to_github.sh"
echo "============================================================"