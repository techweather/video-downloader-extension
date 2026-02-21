"""
Anonymous error reporting via Discord webhook.
Only called explicitly when the user clicks "Send Report".
"""

import re
import requests
from version import __version__

DISCORD_WEBHOOK_URL = (
    "https://discord.com/api/webhooks/1474267001865240578/"
    "HJ2qkIF_-aHntsVYzhFx8Whp9Y5d0w6HtrVLVK4fi4EloDmomcX4-I4WtSvYPfEMSB4n"
)

_FIELD_LIMIT = 1024  # Discord embed field character limit


def strip_ansi(text: str) -> str:
    """Remove ANSI colour escape codes."""
    return re.sub(r'\x1b\[[0-9;]*m', '', text)


def redact_paths(text: str) -> str:
    """Replace OS usernames in file paths with [user]."""
    text = re.sub(r'/Users/[^/\s]+/', '/Users/[user]/', text)
    text = re.sub(r'C:\\Users\\[^\\s]+\\', r'C:\\Users\\[user]\\', text, flags=re.IGNORECASE)
    return text


def clean_error_text(text: str) -> str:
    """Strip ANSI codes and redact user paths — the full text, not summarised."""
    return redact_paths(strip_ansi(text))


def _split_fields(label: str, text: str) -> list:
    """Split text into one or more embed fields respecting Discord's 1024-char limit."""
    if len(text) <= _FIELD_LIMIT:
        return [{"name": label, "value": text, "inline": False}]

    # Split into chunks; cap at 3 parts (~3 KB) to stay well inside embed limits
    chunks = []
    remaining = text
    while remaining and len(chunks) < 3:
        chunks.append(remaining[:_FIELD_LIMIT])
        remaining = remaining[_FIELD_LIMIT:]
    if remaining:
        chunks[-1] = chunks[-1][:_FIELD_LIMIT - 14] + "\n… [truncated]"

    total = len(chunks)
    return [
        {"name": f"{label} ({i + 1}/{total})", "value": chunk, "inline": False}
        for i, chunk in enumerate(chunks)
    ]


def send_error_report(error_type: str, error_message: str, url: str) -> bool:
    """Send an anonymous error report to the Discord webhook.

    Sends the full error text (ANSI-stripped, paths redacted) so developers
    get actionable information. Returns True on HTTP 204, False otherwise.
    """
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc or "Unknown"
    except Exception:
        domain = "Unknown"

    safe_url = redact_paths(url) if url else "No URL"
    clean_msg = clean_error_text(error_message) if error_message else "No message"

    fields = _split_fields("Error Details", clean_msg)
    fields += [
        {"name": "URL", "value": safe_url[:_FIELD_LIMIT], "inline": False},
        {"name": "Domain", "value": domain, "inline": True},
        {"name": "App Version", "value": __version__, "inline": True},
    ]

    embed = {
        "title": f"Error Report: {error_type}",
        "color": 15158332,  # red
        "fields": fields,
        "footer": {"text": "dlwithit Error Report"},
    }

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=10
        )
        return response.status_code == 204
    except Exception as e:
        print(f"[error_reporter] Failed to send report: {e}")
        return False
