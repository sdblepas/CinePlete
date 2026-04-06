# Contributing to CinePlete

Thank you for taking the time to contribute! This guide covers everything you need to get started.

---

## Prerequisites

- Docker + Docker Compose (for running the full stack)
- Python 3.11+ (for running tests locally without Docker)
- A TMDB API key (v3 classic key — not the Read Access Token)
- Node.js 18+ + Playwright (for e2e tests)

---

## Running locally

```bash
# Clone the repo
git clone https://github.com/sdblepas/CinePlete.git
cd CinePlete

# Start with Docker Compose
docker compose up -d

# Or bare Python (no Docker)
pip install -r requirements.txt
python -m uvicorn app.web:app --reload --port 8787
```

Open `http://localhost:8787` and configure your media server in the Config tab.

---

## Running the test suite

```bash
# Unit tests
pip install -r requirements.txt
pytest tests/ -v

# End-to-end tests (Playwright)
cd e2e
npm install
npx playwright install chromium
npx playwright test
```

All tests must pass before opening a PR.

---

## Branch naming

| Type | Pattern | Example |
|------|---------|---------|
| New feature | `feat/short-description` | `feat/emby-support` |
| Bug fix | `fix/short-description` | `fix/localhost-warning` |
| Feature branch (larger) | `feature-name` | `feature-emby` |
| Docs only | `docs/short-description` | `docs/update-readme` |

**Never push directly to `main`.** Always open a PR.

---

## Commit message convention

CinePlete uses conventional commits — the CI pipeline uses these to auto-bump the version:

| Prefix | Effect | Example |
|--------|--------|---------|
| `feat:` | Minor version bump | `feat: add Telegram notifications` |
| `fix:` | Patch version bump | `fix: stale actor cache after rescan` |
| `chore:` | No version bump | `chore: update dependencies` |
| `docs:` | No version bump | `docs: update README` |
| `test:` | No version bump | `test: add Emby unit tests` |
| `feat!:` | **Major** version bump | `feat!: add Emby media server support` |

Add `[skip ci]` to the commit message for documentation-only changes that don't need a Docker build.

---

## Pull request checklist

Before opening a PR, make sure:

- [ ] `pytest tests/` passes locally
- [ ] Playwright e2e tests pass (if UI was changed)
- [ ] Both `README.md` **and** `README.fr.md` are updated if the feature affects docs
- [ ] No API keys, tokens, or secrets are committed
- [ ] No `localhost` URLs in config examples (use `192.168.1.x` or service names)
- [ ] Branch targets `main`
- [ ] Commit messages follow the convention above

---

## What not to do

- Do not commit `.env` files, `config.yml` with real credentials, or any API keys
- Do not use `localhost` in documentation or config examples — it breaks inside Docker
- Do not skip tests (`--no-verify`) unless you have a very good reason and say so in the PR
- Do not open a PR against an old feature branch — always target `main`

---

## Reporting bugs

Use the **Bug Report** issue template. Include your CinePlete version (shown in the sidebar), media server type, install method, and the relevant lines from the **Logs tab**.

## Suggesting features

Use the **Feature Request** issue template. Describe the problem you're solving, not just the solution.
