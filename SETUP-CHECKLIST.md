# Kingdom Circuit setup checklist

## 1. Upload the package

Delete the old test files in the repository, then upload every file and folder from this package into the repository root.

## 2. Change GitHub Pages to GitHub Actions

Go to **Settings > Pages**. Under **Build and deployment**, change **Source** from **Deploy from a branch** to **GitHub Actions**.

## 3. Add the optional Ticketmaster key

The official-site checker runs without a key. Ticketmaster substantially improves coverage.

Go to **Settings > Secrets and variables > Actions > New repository secret**.

- Name: `TICKETMASTER_API_KEY`
- Secret: your Ticketmaster Consumer Key

Never put the key into a public file.

## 4. Run the collector once

Go to **Actions > Update and deploy show calendar > Run workflow**.

## 5. Confirm the site

Open:

`https://84lorinw-a11y.github.io/kingdom-circuit/`

The same workflow will run automatically every day.
