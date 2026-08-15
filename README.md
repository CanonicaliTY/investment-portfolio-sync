# Trading 212 Portfolio Sync

A small, read-only Python app that exports a Trading 212 Invest or Stocks ISA portfolio to a clean JSON file.

It is useful for personal dashboards, backups, automations, and AI-assisted portfolio reviews.

```text
Trading 212 → portfolio/latest.json → your own tools
```

## Safety first

- Uses only five documented `GET` endpoints.
- Cannot place or cancel orders.
- Reads credentials only from environment variables or GitHub Secrets.
- Never includes credentials or API error bodies in the snapshot.

The generated snapshot contains private financial information. Keep any repository that stores a real snapshot **private**.

## Recommended setup

Do not fork this public repository if you need a private copy: public forks normally remain public.

Instead, click **Use this template → Create a new repository**, then choose **Private**. This gives you an independent repository that can safely store your snapshot and Secrets.

### 1. Create read-only Trading 212 credentials

Create a dedicated API key in Trading 212 with only the permissions needed to read account data, positions, orders, and history. Do not enable trading or modification permissions.

### 2. Add GitHub Secrets

In your new private repository, open:

**Settings → Secrets and variables → Actions → New repository secret**

Add:

- `T212_API_KEY`
- `T212_API_SECRET`

Never put the values in `.env.example`, source code, issues, or chat messages.

### 3. Run the sync

Open **Actions → Portfolio sync → Run workflow**.

The workflow updates `portfolio/latest.json` and commits it only when the content changes.

If the workflow cannot push, enable **Settings → Actions → General → Workflow permissions → Read and write permissions**.

## Run locally

Requires Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
```

Add your credentials to `.env`, load them, and run the sync:

```bash
set -a
source .env
set +a
python -m trading212_sync
```

`.env` is ignored by Git. The application does not load it automatically.

## Optional daily schedule

The public template is manual by default so it does not make assumptions about your timezone or review routine.

To enable a daily sync, add a `schedule` entry under `on` in `.github/workflows/portfolio-sync.yml`:

```yaml
on:
  workflow_dispatch:
  schedule:
    - cron: "0 18 * * *"
```

GitHub cron uses UTC and scheduled runs can be delayed. Adjust the expression for your timezone and daylight-saving requirements.

## Snapshot contents

`portfolio/latest.json` contains:

- account currency, cash, invested value, and profit/loss;
- positions, prices, values, weights, and original Trading 212 tickers;
- pending orders;
- recent historical orders and transactions when permitted;
- a UTC generation timestamp and sync status.

Unavailable values are `null`; the application does not guess them. Optional history failures do not prevent the core portfolio snapshot from being written.

## Development

Tests use mocked HTTP responses and never require real credentials:

```bash
python -m unittest discover -s tests -v
```

See [SECURITY.md](SECURITY.md) for the threat model and credential-handling details.

This project uses the official Trading 212 Public API documentation for [authentication](https://docs.trading212.com/api/section/authentication/building-the-authorization-header), [account summaries](https://docs.trading212.com/api/accounts/getaccountsummary), [positions](https://docs.trading212.com/api/positions), [pending orders](https://docs.trading212.com/api/orders/orders), and [pagination](https://docs.trading212.com/api/section/pagination).


## Disclosure of Delegation to Generative AI

The authors declare the use of generative AI in the research and writing process. According to the GAIDeT taxonomy (2025), the following tasks were delegated to GAI tools under full human supervision:

- Code generation
- Code optimization
- Text generation

The GAI tool used were: Chat-GPT-5.6 Sol.
Responsibility for the final manuscript lies entirely with the authors.
GAI tools are not listed as authors and do not bear responsibility for the final outcomes.
Declaration submitted by: Tingyu Chen