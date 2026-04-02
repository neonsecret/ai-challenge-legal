# Czech Supreme Court Case Law Sync

## Overview

The caselaw sync downloads and indexes decisions from rozhodnuti.nsoud.cz into the
`court_decisions` PostgreSQL table. The agent uses this table via `search_court_decisions`
and `fetch_court_decision` tools.

---

## court_decisions Table Schema

```sql
CREATE TABLE court_decisions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ecli            TEXT UNIQUE NOT NULL,
    case_number     TEXT NOT NULL,
    court           TEXT NOT NULL DEFAULT 'Nejvyssi soud',
    decision_date   DATE,
    decision_type   TEXT,              -- 'rozsudek' / 'usneseni'
    category        TEXT,              -- A-E
    legal_thesis    TEXT,              -- pravni veta
    judges          TEXT,
    full_text       TEXT,              -- full Anotace, fetched on demand
    full_text_fetched BOOLEAN NOT NULL DEFAULT FALSE,
    source_url      TEXT,
    source_unid     TEXT,              -- Domino UNID
    regulations     JSONB,             -- [{"paragraph":"52","law_number":262,"law_year":2006}]
    keywords        TEXT[],
    search_vector   TSVECTOR,          -- auto-populated by trigger
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_court_decisions_search ON court_decisions USING GIN (search_vector);
CREATE INDEX idx_court_decisions_regulations ON court_decisions USING GIN (regulations);
CREATE INDEX idx_court_decisions_date_desc ON court_decisions (decision_date DESC);
CREATE INDEX idx_court_decisions_category ON court_decisions (category);
```

The `search_vector` is auto-populated by a PostgreSQL trigger on INSERT/UPDATE of
`legal_thesis`, `case_number`, or `keywords` columns. Tokenizer: `simple` (language-agnostic,
preserves Czech legal terms that stemmers would mangle).

To recreate from scratch: `uv run python -c "import asyncio; from neolex.db.postgres import init_db; asyncio.run(init_db())"`

---

## Scraper Script

**Location:** `scripts/scrape_supreme_court.py`

### Modes

#### Bulk download (initial population)

```bash
# Download all decisions 2010–2026 with metadata enrichment (takes ~30–60 minutes)
uv run python scripts/scrape_supreme_court.py --mode bulk --from-year 2010 --to-year 2026

# Fast bulk without individual page fetch (list-page data only, faster but ECLI is synthetic)
uv run python scripts/scrape_supreme_court.py --mode bulk --from-year 2010 --to-year 2026 --no-enrich
```

#### Daily sync

```bash
# Sync decisions from last 7 days (default)
uv run python scripts/scrape_supreme_court.py --mode sync --days 7

# Sync last 30 days
uv run python scripts/scrape_supreme_court.py --mode sync --days 30
```

#### Fetch full text for a specific decision

```bash
uv run python scripts/scrape_supreme_court.py --mode fetch-text --ecli ECLI:CZ:NS:2024:4.TDO.621.2024.1
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | required | `bulk`, `sync`, or `fetch-text` |
| `--from-year` | 2010 | Start year for bulk mode |
| `--to-year` | current year | End year for bulk mode |
| `--days` | 7 | Days to look back in sync mode |
| `--ecli` | — | ECLI for fetch-text mode |
| `--no-enrich` | false | Skip individual page fetches in bulk mode |
| `--concurrency` | 5 | Concurrent individual page fetches |
| `--log-level` | INFO | Logging verbosity |

---

## Launchd Plist (macOS)

**File:** `app.vitreon.caselaw-sync.plist` (project root)

Runs daily at 03:00 in sync mode (last 7 days).

### Install

```bash
cp app.vitreon.caselaw-sync.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/app.vitreon.caselaw-sync.plist
```

### Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/app.vitreon.caselaw-sync.plist
rm ~/Library/LaunchAgents/app.vitreon.caselaw-sync.plist
```

### Check status

```bash
launchctl list | grep caselaw
tail -50 /tmp/vitreon-caselaw-sync.log
```

---

## Initial Bulk Download

After deploying for the first time, run the bulk download:

```bash
# Step 1: Verify DB is ready
uv run python -c "
import asyncio
from neolex.db.court_decisions import get_decisions_count
print('Count:', asyncio.run(get_decisions_count()))
"

# Step 2: Run bulk download (with enrichment for real ECLIs)
uv run python scripts/scrape_supreme_court.py \
  --mode bulk \
  --from-year 2010 \
  --to-year 2026 \
  --concurrency 5 \
  --log-level INFO

# Step 3: Verify
psql $DATABASE_URL -c "
SELECT
    count(*) as total,
    count(*) FILTER (WHERE category = 'A') as landmark,
    count(*) FILTER (WHERE decision_date > '2020-01-01') as recent,
    count(*) FILTER (WHERE full_text_fetched = true) as has_full_text
FROM court_decisions;
"
```

---

## Verify Sync Is Working

```sql
-- Check decisions added today
SELECT count(*) FROM court_decisions WHERE created_at > now() - interval '1 day';

-- Check most recent decisions
SELECT ecli, case_number, category, decision_date
FROM court_decisions
ORDER BY created_at DESC
LIMIT 5;

-- Check BM25 search works
SELECT case_number, category, decision_date
FROM court_decisions
WHERE search_vector @@ plainto_tsquery('simple', 'vypovedni lhuta zamestnavatel')
ORDER BY ts_rank(search_vector, plainto_tsquery('simple', 'vypovedni lhuta zamestnavatel')) DESC
LIMIT 5;
```

---

## Environment Requirements

- `DATABASE_URL` — asyncpg-format PostgreSQL URL (set via `.env`)
- Network access to `rozhodnuti.nsoud.cz` (HTTPS, no auth required)
- PostgreSQL with `pgvector` extension (for `init_db`)

---

## Migration Notes (GCP / Hetzner)

| macOS | GCP / Hetzner |
|-------|---------------|
| launchd plist | systemd timer or Cloud Scheduler |
| `StartCalendarInterval` | cron expression `0 3 * * *` |
| `~/Library/LaunchAgents/` | `/etc/systemd/system/` |

### systemd timer equivalent

```ini
# /etc/systemd/system/vitreon-caselaw-sync.timer
[Unit]
Description=Daily Czech case law sync

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/vitreon-caselaw-sync.service
[Unit]
Description=Czech case law sync

[Service]
Type=oneshot
WorkingDirectory=/srv/vitreon
ExecStart=/usr/local/bin/uv run python scripts/scrape_supreme_court.py --mode sync --days 7
StandardOutput=journal
StandardError=journal
```

---

## Future Extensions

- **Constitutional Court** (nalus.usoud.cz): ASP.NET ViewState, medium difficulty
- **Supreme Administrative Court** (vyhledavac.nssoud.cz): CSRF tokens, medium difficulty
- **Lower courts** (rozhodnuti.justice.cz): 573K civil decisions via REST API, easy

Each can be added as an independent scraper + agent tool without architectural changes
(separate DB table per court type, separate agent tool).
