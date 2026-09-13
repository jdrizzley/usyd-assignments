# Going live on GitHub Pages

This guide takes the project from a folder on your computer to a public website at
`https://<your-github-username>.github.io/<repository-name>/`, with the scraper refreshing the
data every night. It costs nothing. It assumes you have never deployed a website before, so it
names every menu and button. Budget about 30 minutes for the first pass, most of it waiting for
the first scrape.

Where you see `jdrizzley` and `usyd-assignments` below, substitute your own username and
repository name if they differ.

---

## Part 1: Put the code on GitHub

### 1. Create a GitHub account (skip if you have one)

1. Go to <https://github.com> and click **Sign up** in the top right.
2. Follow the prompts. The free plan is all you need.

### 2. Make sure the repository exists on GitHub

This project's folder is already linked to `https://github.com/jdrizzley/usyd-assignments`. Open
that address in your browser. If you see the repository, continue to step 3. If you see a 404:

1. Click the **+** icon in the top right of any GitHub page and choose **New repository**.
2. In **Repository name** type `usyd-assignments`.
3. Leave **Public** selected. GitHub Pages is free only for public repositories.
4. Do **not** tick "Add a README file".
5. Click **Create repository**.

### 3. Commit and push the files

Open a terminal in the project folder (in VS Code: **Terminal → New Terminal**; on Linux or
macOS: open Terminal and `cd` into the folder). Run these four commands one at a time:

```
git add -A
git commit -m "Build USyd assessment calendar"
git branch -M main
git push -u origin main
```

If `git push` asks for a username and password, the password must be a **personal access token**,
not your GitHub password: on GitHub click your avatar (top right) → **Settings** → scroll to
**Developer settings** (bottom of the left sidebar) → **Personal access tokens** → **Tokens
(classic)** → **Generate new token (classic)** → tick the `repo` and `workflow` boxes → **Generate
token**, and paste the token when asked for a password. Alternatively install
[GitHub Desktop](https://desktop.github.com/), choose **File → Add local repository**, pick the
folder, write a summary in the bottom-left box, click **Commit to main**, then **Push origin**.

Check: reload `https://github.com/jdrizzley/usyd-assignments`. You should see `index.html`,
`scraper/`, `data/` and the other files listed.

---

## Part 2: Let the scraper commit to the repository

The nightly job writes new data files back into the repository. GitHub blocks that by default.

1. On the repository page, click the **Settings** tab (the rightmost tab, with a cog icon).
2. In the left sidebar, click **Actions**, then **General** underneath it.
3. Scroll to the bottom section **Workflow permissions**.
4. Select **Read and write permissions**.
5. Click **Save** just below that section.

Optional but polite: give the scraper a contact address in its `User-Agent`.

1. Still in **Settings**, in the left sidebar click **Secrets and variables**, then **Actions**.
2. Click the **Variables** tab (next to "Secrets").
3. Click **New repository variable**.
4. **Name**: `USYD_CONTACT`. **Value**: an email address you check.
5. Click **Add variable**.

---

## Part 3: Turn on GitHub Pages

1. Click the **Settings** tab again.
2. In the left sidebar, under "Code and automation", click **Pages**.
3. Under **Build and deployment**, find **Source** and make sure **Deploy from a branch** is
   selected.
4. Under **Branch**, use the first dropdown (it says "None") to choose **main**.
5. In the second dropdown next to it choose **/ (root)**. Not `/docs`.
6. Click **Save**.

A blue box appears saying "Your site is ready to be published". Wait one to two minutes, then
reload the page. It changes to "Your site is live at https://jdrizzley.github.io/usyd-assignments/".

Check: click **Visit site**. You should see the page with the term ruler, "Nothing due yet." and
the unit picker. The site already ships with a starter set of unit data, so try typing `AMME`
into **Add a unit**. If the header says "Loading sessions" for more than a few seconds, wait
another minute and reload: Pages sometimes serves the first deploy in two stages.

---

## Part 4: Run the first scrape by hand

Rather than waiting for 03:00 Sydney time, trigger it now. Start with a small run to prove
everything works end to end, then do the full one.

### 4a. Small test run (about 10 minutes)

1. Click the **Actions** tab at the top of the repository.
2. If you see a button **I understand my workflows, go ahead and enable them**, click it.
3. In the left sidebar, click **Scrape unit outlines**.
4. On the right, click the grey **Run workflow** dropdown button.
5. Leave **Use workflow from** on `main`. Leave **Target year** as it is. In **Only scrape the
   first N unit codes** type `200`. Leave **force** empty.
6. Click the green **Run workflow** button.
7. After a few seconds a new row appears with a yellow dot. Click it, then click the **scrape**
   box to watch the log. The steps are: install, tests, scrape, commit.

When the dot turns into a green tick, the run succeeded. If it shows a red cross, jump to Part 6.

A limited run like this does not throw away the data already in the repository. The units it
scraped are refreshed and every other unit is kept, so the site stays complete while you test.

Check that the data was committed: click the **Code** tab. The most recent commit at the top of
the file list should be from **scraper-bot** and titled `data: refresh 2026-...`. Click into
`data/` and confirm `meta.json` has today's date in `generatedAt`.

Then check the site picked it up: wait two minutes (Pages redeploys after each commit), open
your site, hard-refresh (**Ctrl+Shift+R**, or **Cmd+Shift+R** on a Mac), and look at the
disclaimer at the bottom of the rail. "Updated" should show today's date.

### 4b. Full run (about 2 to 3 hours)

Repeat the steps in 4a but leave **Only scrape the first N unit codes** empty. The job crawls
roughly 7,600 unit landing pages plus every published outline at one request per second. That
is deliberately slow to be polite to the University's servers. Do not change it.

You do not have to keep the browser open. When the run finishes, the site updates itself.

From now on the job runs automatically every night at 03:00 Sydney time (04:00 during daylight
saving). You can see every run under the **Actions** tab.

---

## Part 5: Confirm the whole thing works

1. Open the site on your phone as well as your laptop.
2. Add two units you are enrolled in. The list should merge them in date order, with each unit
   marked by its own swatch shape and colour.
3. Click **Download .ics**, then open the downloaded file. On a Mac it opens in Calendar; on
   Windows, double-click it to add to Outlook; for Google Calendar, go to
   <https://calendar.google.com> → cog icon → **Settings** → **Import & export** → **Select file
   from your computer**.
4. Copy the page's address after adding units. It contains `?s=...&u=...`. Anyone who opens that
   link sees the same selection, so it is a good thing to share with classmates.

---

## Part 6: When something doesn't work

**The site shows "Couldn't load unit data."**
The page could not fetch `data/index.json`. Either Pages has not finished deploying (wait two
minutes and click **Try again**), or the `data/` folder is missing from the `main` branch. Look
in the **Code** tab; if `data/` is not there, run the workflow (Part 4a).

**The site shows the GitHub 404 page, not the styled "Week 14." page.**
Pages is not enabled or is pointed at the wrong branch or folder. Redo Part 3 and confirm the
dropdowns say **main** and **/ (root)**.

**The styled "Week 14." page appears when opening the site's main address.**
The repository was renamed or moved to a user site. Open `404.html` and `index.html` and change
`/usyd-assignments/` in the `og:image` and asset links to the new path.

**The workflow run has a red cross on the "Parser tests" step.**
The University changed their outline HTML. Nothing has been overwritten; the site keeps serving
the last good data. Follow "When a run fails" in `README.md`: refresh the fixture file, fix the
parser, push, and rerun.

**The run is red on the "Scrape" step and the log ends with `BUILD FAILED`.**
Read the bullet points under it. Each names the threshold that tripped, for example "only 412
units with a current outline (< 500)". Early in a semester, before outlines are published, a
full run can legitimately find too few outlines; wait until two weeks before teaching starts and
rerun. If a full run found far fewer units than the previous data and you are sure that is
expected, rerun with the **force** input set to `yes`. (A limited test run never trips this
check on its own, because it is merged into the existing data rather than replacing it.)

**The run is red on the "Commit data" step with a permissions error.**
Part 2 was skipped. Set **Workflow permissions** to **Read and write permissions** and rerun.

**The run is red with "Resource not accessible by integration" or "403".**
Same fix as above.

**The run is cancelled or times out.**
A run has a five and a half hour limit. If the University's site was slow, rerun; the on-disk
cache is not kept between runs, so it starts from scratch, but that is fine.

**The workflow never runs on its own.**
GitHub pauses scheduled workflows on repositories with no activity for 60 days. Open the
**Actions** tab, click **Scrape unit outlines**; if there is a banner saying the schedule is
disabled, click **Enable workflow**. Any push to the repository also re-enables it.

**Week-only dates look wrong (everything a week off).**
Open `data/weeks.json` and compare each session's `"1"` (the Monday of Week 1) with the
University's key dates page. If it is wrong, create `data/weeks.override.json` with the correct
Mondays, as shown in `README.md`, commit it, and push. The override is kept across every scrape.

**Someone reports a missing or wrong deadline.**
Click the ↗ next to the row to open the outline the date came from. If the outline says
something different from the site, the parser needs a fix. If the outline agrees with the site
but Canvas says otherwise, that is the disclaimer doing its job: Canvas wins.

---

## Alternative: Cloudflare Pages

If you want a custom domain or a faster CDN later: sign in at <https://dash.cloudflare.com>,
choose **Workers & Pages** → **Create** → **Pages** → **Connect to Git**, pick the repository,
leave **Build command** empty, set **Build output directory** to `/`, and click **Save and
Deploy**. Every push (including the scraper's nightly commit) redeploys automatically. The
`og:image` link in `index.html` should then be updated to the new address.
