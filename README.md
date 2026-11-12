# OP This Week

A weekly list of Steam games rated **Overwhelmingly Positive** (95%+ positive from 500+ reviews).
It shows the games that joined the list this week, the full list, and the games that dropped
out and why.

- `pipeline/`: Python job. It finds candidates with SteamSpy, confirms them with Steam's
  official store API (`IStoreBrowseService/GetItems`), compares the result with last week's
  list, and writes JSON to `data/`.
- `site/`: Astro static site that reads `data/` at build time.
- `.github/workflows/weekly.yml`: runs every Monday 06:00 UTC. It runs the pipeline, commits
  `data/` and deploys to GitHub Pages.

## Local development

```sh
# Pipeline (needs uv: https://docs.astral.sh/uv/)
cd pipeline
uv run pytest
uv run python -m op_tracker.main --appids 413150,730,620 --dry-run   # quick check
uv run python -m op_tracker.main --max-pages 2 --dry-run             # small SteamSpy sample
uv run python -m op_tracker.main                                     # full run, ~1.5-2 h, writes ../data

# Site
cd site
npm install
npm run dev        # uses ../data if it has data, otherwise site/sample-data
```

`OP_DATA_DIR=/some/path npm run dev` points the site at another data folder.

## Deploying to GitHub Pages

1. Push this repo to GitHub, with `main` as the default branch.
2. In **Settings → Pages**, set **Source** to **GitHub Actions**.
3. In **Settings → Actions → General → Workflow permissions**, choose **Read and write permissions**
   so the workflow can commit `data/`.
4. In **Actions → Weekly update → Run workflow**, start the first run. It saves a baseline, so
   "new" and "dropped" entries start appearing from the following week.

## Safety

If Steam or SteamSpy fails partway, or more than 20% of the list would drop out in one week, the
run stops and `data/` is left unchanged. Check the run, then use `--force` locally if the drop
is real.
