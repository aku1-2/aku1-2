"""
calculate_streak.py
Fetches real contribution data from GitHub GraphQL API,
calculates current + longest streak, and updates README.md
- Total contributions = last 365 days (matches GitHub UI)
- Longest streak = all time (fetches from account creation year)
- Current streak = walks back from today
"""

import os
import json
import re
import requests
from datetime import datetime, timedelta, timezone

USERNAME = os.environ.get("GITHUB_USERNAME", "aku1-2")
TOKEN    = os.environ.get("GITHUB_TOKEN", "")

GRAPHQL_URL = "https://api.github.com/graphql"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""

JOIN_QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
  }
}
"""

def fetch_contributions_range(from_dt: str, to_dt: str) -> list[dict]:
    headers = {"Authorization": f"bearer {TOKEN}"}
    resp = requests.post(
        GRAPHQL_URL,
        json={"query": QUERY, "variables": {"login": USERNAME, "from": from_dt, "to": to_dt}},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    weeks = (
        data["data"]["user"]["contributionsCollection"]
            ["contributionCalendar"]["weeks"]
    )
    days = []
    for week in weeks:
        days.extend(week["contributionDays"])
    return days


def get_join_year() -> int:
    headers = {"Authorization": f"bearer {TOKEN}"}
    resp = requests.post(
        GRAPHQL_URL,
        json={"query": JOIN_QUERY, "variables": {"login": USERNAME}},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    created_at = resp.json()["data"]["user"]["createdAt"]
    return datetime.fromisoformat(created_at.replace("Z", "+00:00")).year


def get_all_time_days() -> dict[str, int]:
    """Fetch every contribution day since account creation."""
    today = datetime.now(timezone.utc).date()
    join_year = get_join_year()
    all_days: dict[str, int] = {}
    for year in range(join_year, today.year + 1):
        from_dt = f"{year}-01-01T00:00:00Z"
        to_dt   = f"{year}-12-31T23:59:59Z"
        for day in fetch_contributions_range(from_dt, to_dt):
            all_days[day["date"]] = day["contributionCount"]
    return all_days


def get_last_365_days() -> dict[str, int]:
    """Fetch last 365 days — matches what GitHub UI shows."""
    today = datetime.now(timezone.utc).date()
    from_date = today - timedelta(days=364)
    from_dt = f"{from_date.isoformat()}T00:00:00Z"
    to_dt   = f"{today.isoformat()}T23:59:59Z"
    days_list = fetch_contributions_range(from_dt, to_dt)
    return {d["date"]: d["contributionCount"] for d in days_list}


def calculate_streaks(all_days: dict[str, int], last_365: dict[str, int]):
    today = datetime.now(timezone.utc).date()

    # ── Current streak (from today backwards) ───────────────────────
    current_streak = 0
    check = today
    if all_days.get(str(today), 0) == 0:
        check = today - timedelta(days=1)

    while True:
        ds = str(check)
        if ds not in all_days:
            break
        if all_days[ds] > 0:
            current_streak += 1
            check -= timedelta(days=1)
        else:
            break

    # ── Longest streak (all time) ────────────────────────────────────
    longest_streak = 0
    run = 0
    prev_date = None
    for ds in sorted(all_days.keys()):
        d = datetime.strptime(ds, "%Y-%m-%d").date()
        if all_days[ds] > 0:
            if prev_date and (d - prev_date).days == 1:
                run += 1
            else:
                run = 1
            longest_streak = max(longest_streak, run)
        else:
            run = 0
        prev_date = d

    # ── Total = last 365 days (matches GitHub UI) ────────────────────
    total_last_365 = sum(last_365.values())

    # ── All-time total ───────────────────────────────────────────────
    total_all_time = sum(all_days.values())

    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "total_last_365": total_last_365,
        "total_all_time": total_all_time,
        "last_updated": str(today),
    }


def update_readme(stats: dict):
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()

    new_block = (
        f"<!-- STREAK-START -->\n"
        f"> 🔥 **Current Streak:** {stats['current_streak']} days"
        f" &nbsp;|&nbsp; ⚡ **Longest:** {stats['longest_streak']} days"
        f" &nbsp;|&nbsp; 📅 **Last 365 days:** {stats['total_last_365']}"
        f" &nbsp;|&nbsp; 🗂️ **All time:** {stats['total_all_time']}"
        f" &nbsp;|&nbsp; 🕒 *Updated: {stats['last_updated']}*\n"
        f"<!-- STREAK-END -->"
    )

    if "<!-- STREAK-START -->" in content and "<!-- STREAK-END -->" in content:
        content = re.sub(
            r"<!-- STREAK-START -->.*?<!-- STREAK-END -->",
            new_block,
            content,
            flags=re.DOTALL,
        )
    else:
        if "\n## " in content:
            idx = content.index("\n## ")
            content = content[:idx] + "\n\n" + new_block + content[idx:]
        else:
            content += "\n\n" + new_block + "\n"

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ README updated — streak={stats['current_streak']}, longest={stats['longest_streak']}, last365={stats['total_last_365']}, alltime={stats['total_all_time']}")


def main():
    print(f"Fetching contributions for @{USERNAME}...")

    last_365 = get_last_365_days()
    all_days = get_all_time_days()   # fetches from join year → today

    stats = calculate_streaks(all_days, last_365)
    print(json.dumps(stats, indent=2))

    with open("streak_data.json", "w") as f:
        json.dump(stats, f, indent=2)

    update_readme(stats)


if __name__ == "__main__":
    main()

