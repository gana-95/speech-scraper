"""
src/state.py
------------
Manages a simple JSON state file so the hourly scraper
knows which pagination offset to resume from.
"""

import json
import logging
import os

log = logging.getLogger(__name__)

STATE_FILE = "scraper_state.json"


def load_state() -> dict:
    """
    Load scraper state from disk.
    Returns default state if file doesn't exist.
    """
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
                log.info(f"Loaded state: offset={state.get('offset', 0)}")
                return state
        except (json.JSONDecodeError, IOError) as e:
            log.warning(f"Could not read state file, starting fresh: {e}")

    return {"offset": 0, "total_downloaded": 0}


def save_state(state: dict) -> None:
    """Persist scraper state to disk."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
        log.info(f"Saved state: offset={state.get('offset', 0)}, "
                 f"total_downloaded={state.get('total_downloaded', 0)}")
    except IOError as e:
        log.error(f"Could not save state file: {e}")


def reset_state() -> None:
    """Reset state back to the beginning (offset 0)."""
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
        log.info("State reset.")