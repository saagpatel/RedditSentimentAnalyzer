# RedditSentimentAnalyzer — Portfolio Disposition

**Status:** Release Frozen — Python FastAPI + React analytics service
on `origin/main` with background ingestion daemon (APScheduler),
VADER sentiment scoring, 6h/12h/1d bucketed spike detection, optional
Claude escalation, and macOS Keychain secrets. **First member
of the self-hosted service cluster** — distribution shape is "operator
runs this on a server," not a desktop binary or PWA. (Deploy configs
such as `launchd/` and `nginx/` are **not present** in the committed
tree.)

> Disposition uses strict `origin/main` verification.
> **Introduces a new disposition cluster** for self-hosted services
> shipped via launchd + nginx (rather than Apple signing or static
> host).

---

## Verification posture

This repo has **only `origin`** (`saagpatel/RedditSentimentAnalyzer`)
— no `legacy-origin` remote. Clean migration state. Local clone's
`main` is tracking `origin/main` correctly.

Specifically verified on `origin/main`:

- Substantive commits on `origin/main`:
  - `87c359e` feat: implement full Reddit Sentiment Analyzer (Phases 0-3)
  - `7e045da` feat: add GitHub Actions CI workflow
- Tree on `origin/main`:
  - `backend/` — Python FastAPI service
  - `frontend/` — React dashboard
  - `pyproject.toml` (uv-managed Python deps)
  - `IMPLEMENTATION-ROADMAP.md`, `CHANGELOG.md`, `CLAUDE.md`,
    `SECURITY.md`, `CONTRIBUTING.md`
  - Note: `launchd/` and `nginx/` deploy configs referenced in the
    original disposition are **not present** in the committed tree.
- Release scaffolding: GitHub Actions CI workflow present
  (`7e045da`); no `RELEASE-READINESS.md`-style runbook
- Default branch: `main`

---

## Current state in one paragraph

RedditSentimentAnalyzer is a Python FastAPI + React analytics service
that polls tracked subreddits every 15 minutes via APScheduler
(seeds with `.hot()` + `.top(week)`, then pulls `.new()`
incrementally), runs VADER sentiment scoring per post and comment,
pre-aggregates into 6-hour buckets with spike detection at 6h / 12h
/ 1d resolution, and surfaces results in a React dashboard with
time-series charts, multi-subreddit comparison, word cloud, and
spike detail panel. Ambiguous posts can optionally escalate to Claude
for deeper classification with reasoning (disabled by default).
Credentials live in macOS Keychain via `keyring` — no `.env` files
with tokens on disk. The background daemon model (APScheduler, 15-minute poll loop) and
macOS Keychain credential storage indicate the operator's intended
distribution shape: operator self-hosts this as a long-running
service on a Mac or Linux box. Deploy configs (`launchd/`, `nginx/`)
are not present in the committed tree and would need to be added
before operator self-hosting.

For full detail see:
- `README.md` on `origin/main`
- `IMPLEMENTATION-ROADMAP.md`

---

## Why "Release Frozen (self-hosted service)" — NOT signing cluster

RedditSentimentAnalyzer is a long-running analytics service, not a
desktop app and not a static site. Distribution shape:

- **No installer, no `.dmg`, no `.app`** — operator runs FastAPI +
  React build behind nginx
- **Background daemon model** — APScheduler keeps polling Reddit
  on a fixed cadence; this requires a persistent host, not a
  static or serverless deployment
- **Background daemon model** — APScheduler keeps polling Reddit
  on a fixed cadence
- **macOS Keychain secrets** — runtime credential model assumes
  macOS host
- **Optional Claude API key** — operator-supplied for escalation

The "gate" is therefore not Apple signing — it's "operator decides
where to host this and what subreddits to track."

This introduces the **third disposition cluster**:

- **Signing cluster** (19+ repos) — Apple-notarized desktop binaries
- **Static-host cluster** (2 repos: PomGambler, HowMoneyMoves) —
  Vercel / Netlify / etc. static SPAs
- **Self-hosted service cluster (new)** — operator runs as a
  long-running service with launchd + nginx (or analogous on
  Linux). RedditSentimentAnalyzer is the first member.

---

## Possible next moves (operator choice)

### Option 1 — Operator self-hosts on Mac mini / VPS

Required scope:

1. Pick host (Mac mini for `launchd/` path-of-least-resistance,
   or VPS for Linux + systemd equivalent)
2. Reddit API credentials in macOS Keychain
3. Optional Claude API key for escalation
4. nginx config + TLS via Certbot or similar
5. Pick subreddits to track
6. Cut v1.0 release tag

Estimated effort: ~3 hours including TLS + Reddit OAuth setup.

### Option 2 — Open-source as a self-host project for others

Polish README install path, document the `launchd/` and `nginx/`
configs as templates. Don't operator-host. Documentation effort
heavier; runtime exposure zero.

Estimated effort: ~2 hours additional README polish.

### Option 3 — Personal-use only, no public release

Operator runs on personal Mac. Keep repo public for transparency but
don't market.

Estimated effort: ~30 minutes (already mostly here).

### Option 4 — Scope down to library + CLI

Drop the FastAPI + React + nginx + launchd stack; ship `vader-spike`
as a Python library + CLI. Different audience (data engineers
building their own pipelines).

Estimated effort: ~1 day refactor.

---

## Recommendation (informational)

**Option 1 (operator self-host)** is probably right — the background
daemon model (APScheduler + FastAPI, macOS Keychain credential storage)
signals that the deployment shape was deliberate, not aspirational.
The marginal cost from "shipped Phases 0-3" to "running on a Mac mini"
is small (author `launchd/` plist + `nginx/` config, then go).

**Option 2 (OSS self-host)** is also strong because the operator
audience is a niche-but-real overlap (data analysts, social-media
researchers, subreddit moderators). Could combine with Option 1 —
operator runs one, README documents how others can run their own.

---

## Portfolio operating system instructions

| Aspect | Posture |
|---|---|
| Portfolio status | `Release Frozen (self-hosted service)` |
| Distribution model | **Long-running service** (FastAPI + APScheduler daemon), NOT desktop, NOT static SPA |
| Review cadence | Suspend overdue counting |
| Resurface conditions | (a) Operator picks Option 1/2/3/4, (b) live service starts producing operational alerts, or (c) operator opens a v1.1 scope packet |
| Do **not** auto-add to signing cluster | Different distribution shape |
| Do **not** auto-add to static-host cluster | Service has a background daemon — static hosts can't run APScheduler |
| **New cluster:** self-hosted service | **First member.** Future repos shipped with `launchd/` or `systemd/` + `nginx/` should batch here. |
| Special concern | **Reddit API rate limits and ToS.** Long-running ingestion needs operator-supplied PRAW credentials with appropriate user-agent. |

---

## Why this row introduces a new cluster

The signing cluster and static-host cluster cover desktop binaries
and static SPAs. Neither fits RedditSentimentAnalyzer:

- **Signing cluster fit:** no, because the runtime is a server
  process, not an installable app.
- **Static-host cluster fit:** no, because static hosts can't run
  the APScheduler ingestion loop or expose the FastAPI service.

The self-hosted service cluster takes its release-readiness shape
from the persistent-daemon model (APScheduler + FastAPI, macOS
Keychain credential storage). Future candidate signals: presence of
`launchd/` plists, `Dockerfile`, `systemd/` units, or `fly.toml` /
similar PaaS configs.

---

## Reactivation procedure (for the next code session)

1. Verify `git branch -vv` shows `main` tracking `origin/main`.
   Already correct as of this disposition pass.
2. Review the local stash (`r10-reddit-stash`) — contains any
   uncommitted work from before this pass.
3. Re-run `uv sync && cd frontend && npm install` to confirm
   toolchain.
4. If self-hosting: author `launchd/` plist and `nginx/` config
   (these are not present in the committed tree).
5. **Pick Option 1/2/3/4 before public README polish.**

---

## Last known reference

| Field | Value |
|---|---|
| Last substantive commit | `87c359e` feat: implement full Reddit Sentiment Analyzer (Phases 0-3) |
| Default branch | `main` |
| Build system | Python (uv) + FastAPI + React + APScheduler + VADER + Reddit PRAW + keyring (macOS Keychain) |
| Deploy config on `origin/main` | None committed — launchd/nginx configs referenced in original disposition are not present in tree |
| CI | GitHub Actions workflow (`7e045da`) |
| Release scaffolding | CI workflow only; no runbook docs |
| Distribution shape | **Self-hosted service** with launchd + nginx |
| AI integration | Optional Claude escalation for ambiguous posts (operator-supplied API key, disabled by default) |
| Secret storage | macOS Keychain via `keyring` — no on-disk `.env` tokens |
| Migration state | **No `legacy-origin` remote** — clean |
| Distinguishing feature | **First self-hosted service cluster member.** Distribution shape introduced this session. |
