# Launch NextUp PNW entirely from your phone

These instructions create the complete public repository in **one initial commit**. Later automated commits are expected: they are how the service refreshes its listings.

You need the downloaded `nextup-pnw-production.zip`, a GitHub account, Safari or Chrome, and roughly 15 minutes. You do not need a computer, paid hosting, a domain, or an API key.

## Part 1 — Create a blank cloud workspace

1. Download `nextup-pnw-production.zip` to the Files app on your phone.
2. In your browser, sign in at [github.com](https://github.com).
3. Go to [github.com/codespaces](https://github.com/codespaces).
4. Find **Explore quick start templates**. Tap **See all** if necessary.
5. Under **Blank**, tap **Use this template**.
6. Wait for the browser-based editor to open.
7. If the editor is cramped, rotate your phone sideways and use the browser's **Request Desktop Website** option.

GitHub includes a monthly Codespaces allowance for personal accounts. This upload should use only a few minutes. Delete the Codespace after launch so it cannot consume storage later.

## Part 2 — Upload the finished repository

1. Tap the Explorer/files icon near the upper-left side of the editor.
2. Tap the three-dot menu at the top of the Explorer.
3. Choose **Upload…**.
4. Select `nextup-pnw-production.zip` from the Files app.
5. Open the terminal using the menu button, then **Terminal → New Terminal**.
6. Paste these two lines:

```bash
unzip -o nextup-pnw-production.zip
rm nextup-pnw-production.zip
```

The second command removes only the uploaded ZIP from the temporary cloud workspace. It does not remove the extracted project.

## Part 3 — Publish everything as one commit

Paste this exact block into the terminal:

```bash
git init -b main
git add .
git commit -m "Launch NextUp PNW"
gh repo create nextup-pnw --public --source=. --remote=origin --push
```

If GitHub asks whether the GitHub CLI may use your account, approve it. When the command finishes, visit `https://github.com/YOUR-USERNAME/nextup-pnw`.

The repository should show exactly one commit named **Launch NextUp PNW**.

### If you already created an empty repository

Use this block instead of the final `gh repo create` command. Replace `YOUR-USERNAME` only in the URL:

```bash
git init -b main
git add .
git commit -m "Launch NextUp PNW"
git remote add origin https://github.com/YOUR-USERNAME/nextup-pnw.git
git push -u origin main
```

Do not initialize the empty GitHub repository with a README, license, or `.gitignore`, because doing so creates an extra commit.

## Part 4 — Enable the public website

Use GitHub in your phone browser, not the GitHub mobile app, for these settings.

1. Open the `nextup-pnw` repository.
2. Tap **Settings**. On a narrow screen, it may be inside the repository's horizontal tab menu.
3. Under **Code and automation**, open **Pages**.
4. Under **Build and deployment**, set **Source** to **GitHub Actions**.
5. Return to the repository and open **Actions**.
6. Open **Deploy GitHub Pages**.
7. If the first run failed because Pages was not enabled yet, tap **Re-run jobs → Re-run all jobs**.
8. Wait for the green check mark.

Your public address will be `https://YOUR-USERNAME.github.io/nextup-pnw/`.

The deployment workflow automatically uses your actual GitHub username. You do not have to edit URLs in the website.

## Part 5 — Give the updater permission to save changes

1. In the repository, go to **Settings → Actions → General**.
2. Scroll to **Workflow permissions**.
3. Select **Read and write permissions**.
4. Tap **Save**.

This lets the repository's own updater commit refreshed data. The workflows request only the specific permissions they need.

## Part 6 — Confirm Issues and submissions

1. Go to **Settings → General**.
2. Under **Features**, make sure **Issues** is checked.
3. Return to the public website.
4. Tap **Submit an opportunity**.
5. GitHub should open a form titled **Submit an opportunity** with fields for career field, type, official link, location, ISO-formatted date, eligibility, and reason.

Submitted links are checked automatically. High-confidence events with machine-readable details are added directly. When an official page lacks structured data, the verifier can conservatively match the submitted title and ISO date against the page. Duplicates and rejected resources receive an explanation; ambiguous pages stay open instead of being published as fact.

## Part 7 — Test the automation once

1. Open the repository's **Actions** tab.
2. Open **Update opportunities**.
3. Tap **Run workflow**.
4. Leave **Update mode** set to `full`.
5. Tap the green **Run workflow** button.
6. Refresh after a minute and open the new run.

A successful run shows green checks for verification, discovery, tests, build, save, and deployment. It may create an automated data-update commit. That is normal and happens after your one-commit launch.

## Normal schedule

- Every day: verify links, refresh verification dates, and archive expired listings.
- Every Sunday: scan all enabled sources for newly announced opportunities.
- Whenever someone submits: verify the official source and publish strong matches.

GitHub may start scheduled workflows several minutes late during busy periods. The schedule does not require your phone to be on.

## Delete the temporary Codespace

After the repository is online, return to [github.com/codespaces](https://github.com/codespaces), open the blank Codespace's three-dot menu, and choose **Delete**. Deleting it does not delete your repository or website.

## Optional custom domain

You do not need one. The free `github.io` URL works permanently. If you buy a domain later, add it under **Settings → Pages → Custom domain** and set a `SITE_URL` repository variable so generated canonical URLs use it.

## Troubleshooting

### The Pages workflow has a red X

Enable **Settings → Pages → GitHub Actions**, then re-run the workflow. Also confirm the repository is public.

### The updater says it cannot push

Enable **Settings → Actions → General → Read and write permissions** and re-run it.

### The submission button opens a missing page

Confirm Issues are enabled. The generated GitHub Pages build uses the repository owner automatically on every deployment.

### The ZIP extracted into a folder

In the terminal, run `ls`. If you see a folder named `nextup-pnw-production`, run:

```bash
cp -a nextup-pnw-production/. .
rm -r nextup-pnw-production
```

The target is the explicitly named extracted folder inside the temporary Codespace.

### A source keeps failing

Temporary failures are logged in `data/last-run.json` and do not erase existing listings. The next scheduled run retries it. Sites that block collection are skipped rather than bypassed.

### A submission stays open

The official page probably does not expose machine-readable event data and the title or ISO date could not be matched confidently. The system intentionally avoids publishing it as verified. Editing the issue with a stronger official registration link or a date like `2026-10-17` triggers another check.
