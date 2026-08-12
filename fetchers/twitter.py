"""
Twitter / X fetcher — OPTIONAL.

X's API has required an API key/bearer token (with paid tiers for meaningful
volume) since 2023, so there is no keyless path here. If TWITTER_BEARER_TOKEN
is set, this pulls recent tweets for the accounts in config.TWITTER_WATCHLIST.
Otherwise it returns an "unavailable" marker with a suggested manual-check
list so the report still tells you where to look.
"""
import json
import urllib.request
import urllib.error

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

RECENT_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"


def _search(username, max_results=5):
    query = urllib.request.quote(f"from:{username} -is:retweet")
    url = f"{RECENT_SEARCH_URL}?query={query}&max_results={max_results}&tweet.fields=created_at,public_metrics"
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {config.TWITTER_BEARER_TOKEN}"}
    )
    with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read().decode("utf-8"))


def snapshot():
    if not config.TWITTER_BEARER_TOKEN:
        return {
            "available": False,
            "reason": "No TWITTER_BEARER_TOKEN configured — add one (X API v2) to "
                      "pull live posts. In the meantime, check these accounts manually:",
            "watchlist": [f"https://x.com/{u}" for u in config.TWITTER_WATCHLIST],
            "accounts": {},
        }

    accounts = {}
    errors = []
    for username in config.TWITTER_WATCHLIST:
        try:
            data = _search(username)
            accounts[username] = data.get("data", [])
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            errors.append(f"{username}: {e}")

    if not accounts:
        return {
            "available": False,
            "reason": "TWITTER_BEARER_TOKEN is set but every account fetch failed "
                      f"(likely X's search endpoint requiring a paid tier): "
                      f"{'; '.join(errors[:2]) if errors else 'no data returned'}. "
                      "Check these accounts manually in the meantime:",
            "watchlist": [f"https://x.com/{u}" for u in config.TWITTER_WATCHLIST],
            "accounts": {},
        }

    return {"available": True, "accounts": accounts, "errors": errors}
