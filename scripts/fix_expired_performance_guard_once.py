#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts" / "apply_live_artist_overrides.py"
text = path.read_text(encoding="utf-8")

old = '''        if not match or "Sun, Aug 30, 2026" not in match.group(0) or "Fri, Aug 28, 2026 - 12:00 PM" in match.group(0):
            failures.append("social-club-directory-performance-date-wrong")
    else:
        failures.append("artist-directory-missing")

    social_page = out_dir / "artists" / "social-club-misfits" / "index.html"
    if not social_page.is_file() or "Sun, Aug 30, 2026" not in social_page.read_text(encoding="utf-8", errors="ignore"):
        failures.append("social-club-profile-performance-date-wrong")
'''

new = '''        # The RURAL performance was Aug. 30, 2026. Before/through that date,
        # verify the artist-specific performance date. After it expires, pruning
        # legitimately removes the event, so only reject the old festival-start
        # date if it somehow survives on the artist card.
        card = match.group(0) if match else ""
        today = dt.date.today()
        rural_performance = dt.date(2026, 8, 30)
        if today <= rural_performance:
            if not match or "Sun, Aug 30, 2026" not in card or "Fri, Aug 28, 2026 - 12:00 PM" in card:
                failures.append("social-club-directory-performance-date-wrong")
        elif "Fri, Aug 28, 2026 - 12:00 PM" in card:
            failures.append("social-club-directory-performance-date-wrong")
    else:
        failures.append("artist-directory-missing")

    social_page = out_dir / "artists" / "social-club-misfits" / "index.html"
    if not social_page.is_file():
        failures.append("social-club-profile-missing")
    else:
        social_text = social_page.read_text(encoding="utf-8", errors="ignore")
        today = dt.date.today()
        rural_performance = dt.date(2026, 8, 30)
        if today <= rural_performance:
            if "Sun, Aug 30, 2026" not in social_text:
                failures.append("social-club-profile-performance-date-wrong")
        elif "Fri, Aug 28, 2026 - 12:00 PM" in social_text:
            failures.append("social-club-profile-performance-date-wrong")
'''

if new in text:
    print("Performance-date guard repair already applied.")
elif old in text:
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("Performance-date guard repaired.")
else:
    raise SystemExit("Target performance-date guard block not found")
