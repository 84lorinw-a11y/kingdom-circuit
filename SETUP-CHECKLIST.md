# Replace the current repository with Master v3

1. In GitHub, open `kingdom-circuit` and choose **Code → Add file → Upload files**.
2. Open the downloaded `UPLOAD_TO_REPOSITORY` folder in Finder.
3. Select everything inside that folder and drag it into GitHub. Do not drag the outer folder itself.
4. Confirm paths look like `index.html`, `config/artists.json`, and `scripts/instagram_monitor.py` with no extra folder name in front.
5. Commit directly to `main` with: `Replace site with Kingdom Circuit Master v3`.
6. Open **Actions** and wait for **Update and deploy show calendar** to show a green check.
7. Hard-refresh the live site with **Command + Shift + R**.

Do not delete or replace `.github`. The existing workflow and `TICKETMASTER_API_KEY` secret remain in place.
