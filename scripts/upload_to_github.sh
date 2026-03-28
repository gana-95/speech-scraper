#!/bin/bash
# scripts/upload_to_github.sh
# ----------------------------
# Syncs newly downloaded PDFs to a separate GitHub storage repo.
# Runs daily via cron at midnight.
#
# Prerequisites:
#   - GITHUB_TOKEN set in /etc/environment or .env
#   - PDF_STORAGE_REPO set to "owner/repo" format
#   - git installed on the VM

set -euo pipefail

# ── Load environment ────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env if present (local runs)
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# Validate required variables
if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo "[ERROR] GITHUB_TOKEN is not set. Exiting."
    exit 1
fi

if [ -z "${PDF_STORAGE_REPO:-}" ]; then
    echo "[ERROR] PDF_STORAGE_REPO is not set (expected format: owner/repo). Exiting."
    exit 1
fi

# ── Config ──────────────────────────────────────────────────────────────────
OUTPUT_DIR="${OUTPUT_DIR:-debates}"
SOURCE_DIR="$PROJECT_DIR/$OUTPUT_DIR"
STORAGE_REPO_DIR="/opt/parliament-pdfs"
STORAGE_REPO_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${PDF_STORAGE_REPO}.git"
TODAY=$(date '+%Y-%m-%d')

echo "============================================================"
echo "  Daily PDF Upload  --  $TODAY"
echo "  Source   : $SOURCE_DIR"
echo "  Dest repo: $PDF_STORAGE_REPO"
echo "============================================================"

# ── Clone or update storage repo ────────────────────────────────────────────
if [ ! -d "$STORAGE_REPO_DIR/.git" ]; then
    echo "[INFO] Cloning storage repo..."
    git clone "$STORAGE_REPO_URL" "$STORAGE_REPO_DIR"
else
    echo "[INFO] Pulling latest from storage repo..."
    cd "$STORAGE_REPO_DIR"
    # Update remote URL in case token changed
    git remote set-url origin "$STORAGE_REPO_URL"
    git pull origin main
fi

# ── Sync PDFs (year-based structure preserved) ──────────────────────────────
echo "[INFO] Syncing PDFs..."
rsync \
    --archive \
    --ignore-existing \
    --verbose \
    "$SOURCE_DIR/" \
    "$STORAGE_REPO_DIR/debates/"

# ── Commit and push if there are changes ────────────────────────────────────
cd "$STORAGE_REPO_DIR"

git config user.email "scraper-bot@parliament-scraper"
git config user.name  "Scraper Bot"
git add -A

if git diff --cached --quiet; then
    echo "[INFO] No new PDFs to commit. Nothing to push."
else
    FILE_COUNT=$(git diff --cached --name-only | wc -l)
    git commit -m "data: add $FILE_COUNT PDF(s) scraped on $TODAY"
    git push origin main
    echo "[INFO] Pushed $FILE_COUNT new file(s) to $PDF_STORAGE_REPO"
fi

echo "[INFO] Upload complete at $(date)"