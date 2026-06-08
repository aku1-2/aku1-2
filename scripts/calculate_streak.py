"""
calculate_streak.py
Fetches real contribution data from GitHub GraphQL API,
calculates current + longest streak, and updates README.md
"""

import os
import json
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
        totalContributions
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

def fetch_contributions(year: int) -> list[dict]:
    from_dt = f"{year}-01-01T00:00:00Z"
    to_dt   = f"{year}-12-31T23:59:59Z"
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


def get_all_days() -> dict[str, int]:
    """Return {date_str: count} for current + previous year."""
    today = datetime.now(timezone.utc).date()
    all_days: dict[str, int] = {}
    for year in {today.year - 1, today.year}:
        for day in fetch_contributions(year):
            all_days[day["date"]] = day["contributionCount"]
    return all_days


def calculate_streaks(days: dict[str, int]):
    today = datetime.now(timezone.utc).date()
    sorted_dates = sorted(days.keys(), reverse=True)

    # ── Current streak ──────────────────────────────────────────────
    current_streak = 0
    check = today
    # If today has no contributions yet, start from yesterday
    if days.get(str(today), 0) == 0:
        check = today - timedelta(days=1)

    while True:
        ds = str(check)
        if ds not in days:
            break
        if days[ds] > 0:
            current_streak += 1
            check -= timedelta(days=1)
        else:
            break

    # ── Longest streak ───────────────────────────────────────────────
    longest_streak = 0
    run = 0
    prev_date = None
    for ds in sorted(days.keys()):
        d = datetime.strptime(ds, "%Y-%m-%d").date()
        if days[ds] > 0:
            if prev_date and (d - prev_date).days == 1:
                run += 1
            else:
                run = 1
            longest_streak = max(longest_streak, run)
        else:
            run = 0
        prev_date = d

    # ── Total contributions ──────────────────────────────────────────
    total = sum(days.values())

    # ── First contribution date ──────────────────────────────────────
    active = [ds for ds, c in days.items() if c > 0]
    first_contrib = min(active) if active else str(today)

    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "total_contributions": total,
        "first_contribution": first_contrib,
        "last_updated": str(today),
    }


def update_readme(stats: dict):
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()

    new_block = f"""<!-- STREAK-START -->
> 🔥 **Current Streak:** {stats['current_streak']} days &nbsp;|&nbsp; ⚡ **Longest:** {stats['longest_streak']} days &nbsp;|&nbsp; 📅 **Total Contributions:** {stats['total_contributions']} &nbsp;|&nbsp; 🕒 *Updated: {stats['last_updated']}*
<!-- STREAK-END -->"""

    if "<!-- STREAK-START -->" in content and "<!-- STREAK-END -->" in content:
        import re
        content = re.sub(
            r"<!-- STREAK-START -->.*?<!-- STREAK-END -->",
            new_block,
            content,
            flags=re.DOTALL,
        )
    else:
        # Append before the first H2 or at the end
        if "\n## " in content:
            idx = content.index("\n## ")
            content = content[:idx] + "\n\n" + new_block + content[idx:]
        else:
            content += "\n\n" + new_block + "\n"

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ README updated: streak={stats['current_streak']}, longest={stats['longest_streak']}")


def main():
    print(f"Fetching contributions for @{USERNAME}...")
    days  = get_all_days()
    stats = calculate_streaks(days)

    print(json.dumps(stats, indent=2))

    # Save raw data for optional badge use
    with open("streak_data.json", "w") as f:
        json.dump(stats, f, indent=2)

    update_readme(stats)


if __name__ == "__main__":
    main()
