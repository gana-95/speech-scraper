"""
src/scraper.py
--------------
Downloads Lok Sabha Debate PDFs (English) from:
  https://eparlib.sansad.in/handle/123456789/2963706

Features:
  - Resumes from last offset using scraper_state.json
  - Organises PDFs into debates/YEAR/ subdirectories
  - Supports --limit, --start-date, --end-date, --output-dir
  - Safe to re-run; skips already-downloaded files

Usage:
  python -m src.scraper [options]
  python src/scraper.py [options]

Examples:
  python src/scraper.py --limit 10
  python src/scraper.py --start-date 01-Jan-2025 --end-date 31-Dec-2025
  python src/scraper.py --start-date 01-Jun-2024 --limit 10
"""

import argparse
import logging
import os
import re
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from state import load_state, save_state

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL        = "https://eparlib.sansad.in"
COLLECTION_PATH = "/handle/123456789/2963706"
PAGE_SIZE       = 20
REQUEST_DELAY   = 1.5   # seconds between requests
REQUEST_TIMEOUT = 30    # seconds

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": BASE_URL,
    "Accept-Language": "en-US,en;q=0.9",
}

DATE_FORMATS = ("%d-%b-%Y", "%d-%B-%Y", "%d/%m/%Y", "%Y-%m-%d")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Download Lok Sabha Debate PDFs from the Parliament Digital Library."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch next 10 (resumes from last run)
  python src/scraper.py --limit 10

  # All 2025 debates
  python src/scraper.py --start-date 01-Jan-2025 --end-date 31-Dec-2025

  # At most 10 debates between two dates
  python src/scraper.py --start-date 01-Jun-2024 --end-date 31-Dec-2024 --limit 10

  # Reset state and start from the beginning
  python src/scraper.py --reset
        """,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Maximum number of PDFs to download this run.",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        metavar="DD-Mon-YYYY",
        help="Only download debates on or after this date.",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        metavar="DD-Mon-YYYY",
        help="Only download debates on or before this date.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.getenv("OUTPUT_DIR", "debates"),
        metavar="DIR",
        help="Base folder for PDFs; year subfolders are created automatically.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset saved offset state and start from the beginning.",
    )

    args = parser.parse_args()
    args.start_date = _parse_user_date(args.start_date, "--start-date")
    args.end_date   = _parse_user_date(args.end_date,   "--end-date")

    if args.start_date and args.end_date and args.start_date > args.end_date:
        parser.error("--start-date must be earlier than or equal to --end-date.")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer.")

    return args


def _parse_user_date(value, flag):
    if value is None:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    sys.exit(
        f"Error: could not parse {flag} value '{value}'. "
        "Use DD-Mon-YYYY (e.g. 01-Jan-2025)."
    )


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------
def parse_site_date(date_str):
    """Parse dates as shown on the site e.g. '1-Feb-2025'."""
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def safe_filename(date_str, title):
    """Build a sortable, filesystem-safe filename."""
    dt          = parse_site_date(date_str)
    date_prefix = dt.strftime("%Y-%m-%d") if dt else re.sub(r"[^\w]", "_", date_str)
    safe_title  = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")
    return f"{date_prefix}_{safe_title}.pdf"


def get_year_dir(base_dir, date_str):
    """Return (and create) a year-based subdirectory e.g. debates/2025/"""
    dt   = parse_site_date(date_str)
    year = str(dt.year) if dt else "unknown"
    path = os.path.join(base_dir, year)
    os.makedirs(path, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# HTTP session
# ---------------------------------------------------------------------------
def make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


# ---------------------------------------------------------------------------
# Scraping helpers
# ---------------------------------------------------------------------------
def fetch_listing_page(session, offset):
    url = f"{BASE_URL}{COLLECTION_PATH}?offset={offset}"
    log.info(f"Fetching listing page  offset={offset}")
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def extract_items(soup):
    """Return list of {date, title, item_url} from the collection table."""
    items = []
    table = soup.find("table")
    if not table:
        return items

    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        date  = cells[0].get_text(strip=True)
        title = cells[1].get_text(strip=True)
        link  = cells[3].find("a", href=True)
        if not date or not link:
            continue
        href     = link["href"]
        item_url = (BASE_URL + href) if href.startswith("/") else href
        items.append({"date": date, "title": title, "item_url": item_url})

    return items


def get_pdf_url(session, item_url):
    """Visit an item page and return the PDF bitstream URL, or None."""
    log.info(f"  Visiting item page  ->  {item_url}")
    resp = session.get(item_url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "/bitstream/" in href and (
            href.lower().endswith(".pdf") or "sequence=" in href
        ):
            return (BASE_URL + href) if href.startswith("/") else href

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "/retrieve/" in href:
            return (BASE_URL + href) if href.startswith("/") else href

    return None


def download_pdf(session, pdf_url, save_path):
    """Stream-download a PDF to save_path."""
    resp = session.get(pdf_url, timeout=60, stream=True)
    resp.raise_for_status()
    with open(save_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    size_kb = os.path.getsize(save_path) / 1024
    log.info(f"  Saved  {os.path.basename(save_path)}  ({size_kb:.1f} KB)")


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------
def scrape(session, output_dir, start_date, end_date, limit, reset=False):
    os.makedirs(output_dir, exist_ok=True)

    # Load or reset state
    if reset:
        from src.state import reset_state
        reset_state()
    state = load_state()
    offset = state.get("offset", 0)

    log.info("=" * 60)
    log.info("  Parliament Digital Library  --  Lok Sabha Debates (English)")
    log.info("=" * 60)
    log.info(f"  Resuming from offset : {offset}")
    log.info(f"  Start date           : {start_date.strftime('%d-%b-%Y') if start_date else 'none'}")
    log.info(f"  End date             : {end_date.strftime('%d-%b-%Y')   if end_date   else 'none'}")
    log.info(f"  Limit this run       : {limit if limit else 'unlimited'}")
    log.info(f"  Output dir           : ./{output_dir}/YEAR/")
    log.info("=" * 60)

    total_found      = 0
    total_downloaded = 0
    stop             = False

    while not stop:
        soup  = fetch_listing_page(session, offset)
        items = extract_items(soup)

        if not items:
            log.info("No items on this page -- end of collection.")
            break

        for item in items:
            dt = parse_site_date(item["date"])

            if dt is None:
                log.warning(f"  Cannot parse date '{item['date']}' -- skipping.")
                continue

            # Date-range filter
            if end_date and dt > end_date:
                log.debug(f"  {item['date']} after end-date -- skipping.")
                continue

            if start_date and dt < start_date:
                log.info(
                    f"  {item['date']} is before start-date -- stopping."
                )
                stop = True
                break

            # Limit check
            if limit is not None and total_downloaded >= limit:
                log.info(f"  Reached limit of {limit} -- stopping.")
                stop = True
                break

            total_found += 1
            log.info(f"\n[Match #{total_found}]  {item['date']}  --  {item['title']}")

            year_dir  = get_year_dir(output_dir, item["date"])
            filename  = safe_filename(item["date"], item["title"])
            save_path = os.path.join(year_dir, filename)

            if os.path.exists(save_path):
                log.info("  -> Already downloaded, skipping.")
                continue

            time.sleep(REQUEST_DELAY)
            try:
                pdf_url = get_pdf_url(session, item["item_url"])
            except Exception as e:
                log.error(f"  Could not fetch item page: {e}")
                continue

            if not pdf_url:
                log.warning("  No PDF link found.")
                continue

            time.sleep(REQUEST_DELAY)
            try:
                download_pdf(session, pdf_url, save_path)
                total_downloaded += 1
            except Exception as e:
                log.error(f"  Download failed: {e}")
                if os.path.exists(save_path):
                    os.remove(save_path)

        if not stop:
            has_next = bool(
                soup.find("a", string=re.compile(r"next", re.IGNORECASE))
            )
            if not has_next:
                log.info("No next page -- end of collection.")
                # Reset offset so next run starts fresh from top
                offset = 0
                break
            offset += PAGE_SIZE
            time.sleep(REQUEST_DELAY)

    # Persist updated state
    state["offset"]           = offset
    state["total_downloaded"] = state.get("total_downloaded", 0) + total_downloaded
    save_state(state)

    log.info("\n" + "=" * 60)
    log.info("Run complete.")
    log.info(f"  Matched this run   : {total_found}")
    log.info(f"  Downloaded this run: {total_downloaded}")
    log.info(f"  Lifetime total     : {state['total_downloaded']}")
    log.info(f"  Next run offset    : {state['offset']}")
    log.info("=" * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    args    = parse_args()
    session = make_session()
    scrape(
        session    = session,
        output_dir = args.output_dir,
        start_date = args.start_date,
        end_date   = args.end_date,
        limit      = args.limit,
        reset      = args.reset,
    )