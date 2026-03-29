# NeoLex Incident Response Procedure

**Version:** 1.0
**Date:** 2026-03-26
**Owner:** Engineering

---

## Purpose

This document defines the procedure for detecting, containing, and recovering from
security incidents affecting the NeoLex platform. It is a template — fill in owner
names, contact info, and communication channels before using in production.

---

## Incident Classification

| Severity | Criteria                                                                   | Response SLA |
|----------|----------------------------------------------------------------------------|--------------|
| P1       | Confirmed data breach, unauthorized access to client data, production down | 1 hour       |
| P2       | Suspected breach, API key compromise, degraded availability                | 4 hours      |
| P3       | Suspicious activity (unusual auth failures), dependency vulnerability      | 24 hours     |
| P4       | Low-severity finding, informational                                        | 1 week       |

---

## Contacts

| Role                     | Name | Contact |
|--------------------------|------|---------|
| Incident Commander       | TBD  | TBD     |
| Engineering Lead         | TBD  | TBD     |
| Client Relationship Lead | TBD  | TBD     |
| Legal/Privacy Counsel    | TBD  | TBD     |

---

## Detection Sources

1. **Audit log anomalies** — Elevated `auth_failure` events from a single IP
2. **Rate limit hits** — Repeated 429 responses from one key
3. **Dependency vulnerability scan** — `scripts/audit-deps.sh` output
4. **Secrets scan** — `scripts/scan-secrets.sh` output
5. **External report** — Responsible disclosure from researcher or client

---

## Playbook

### P1/P2: Suspected or Confirmed Breach

**Step 1 — Contain (within 1 hour)**

```bash
# 1. Revoke suspected compromised API key immediately
python -m neolex.admin keys revoke <key_prefix>

# 2. Rotate any system credentials (Anthropic API key, proxy keys)
#    Update .env and restart service

# 3. If server compromise suspected: take server offline
#    docker compose stop neolex
#    OR: disable Tailscale Funnel access
```

**Step 2 — Assess scope**

```bash
# Query audit log for all activity by the compromised key
# (requires admin-scoped API key or direct DB access)
python -c "
import asyncio, json
from neolex.db.audit import get_audit_db

async def main():
    async with get_audit_db() as db:
        rows = await db.get_queries(limit=200)
        for r in rows:
            print(json.dumps(dict(r)))

asyncio.run(main())
"

# Check events table for auth failures, uploads, deletes
sqlite3 neolex.db "SELECT * FROM events WHERE ts > datetime('now', '-7 days') ORDER BY ts DESC;"
```

**Step 3 — Notify**

- Notify affected clients within 72 hours (GDPR requirement, if applicable)
- Prepare incident timeline: when was key created, first used, breach window
- Document all findings in an incident report

**Step 4 — Recover**

```bash
# Issue new API key(s) for affected clients
python -m neolex.admin keys create --name "Replacement key post-incident" --client <slug>

# Verify new key works, revoke old key(s) if not already done
python -m neolex.admin keys list
```

**Step 5 — Post-mortem**

- Schedule post-mortem within 5 business days
- Root cause analysis
- Identify control gaps
- Update this playbook

---

### P3: Suspicious Activity (Elevated Auth Failures)

```bash
# 1. Query auth failure events for the last 24 hours
sqlite3 neolex.db \
  "SELECT ip, COUNT(*) as failures, MIN(ts) as first_seen, MAX(ts) as last_seen
   FROM events
   WHERE event_type = 'auth_failure' AND ts > datetime('now', '-1 day')
   GROUP BY ip
   ORDER BY failures DESC
   LIMIT 20;"

# 2. If one IP is responsible for > 100 failures: block at network level
#    (Tailscale ACL or firewall rule)

# 3. Monitor for 24 hours
# 4. Escalate to P2 if activity continues or client data access is confirmed
```

---

### P3: Dependency Vulnerability Found

```bash
# 1. Run full scan
bash scripts/audit-deps.sh

# 2. Classify severity (CVSS score from output)
# 3. If CVSS >= 7.0 (High) and affects runtime path: treat as P2
# 4. If CVSS < 7.0 or dev-only dependency: treat as P4 (patch next sprint)

# 5. Update dependency
pip install --upgrade <package>
# Update pyproject.toml / requirements files

# 6. Run tests to confirm no regression
python -m pytest tests/neolex/ -v

# 7. Deploy update
```

---

### P3: Secrets Scan Finding in Repository

```bash
# If scripts/scan-secrets.sh reports a finding in a committed file:

# 1. IMMEDIATELY rotate the exposed secret
#    (Anthropic API key, proxy credential, etc.)

# 2. Determine when it was exposed (git log for the file)
git log --all --follow -- <file_path>

# 3. Remove from git history if key was committed
#    (requires force push — coordinate with team)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch <file_path>" \
  --prune-empty --tag-name-filter cat -- --all

# 4. Force-push to remote (requires authorization)
# 5. Document the incident and notify affected services
```

---

## Evidence Preservation

Before any remediation steps that could destroy evidence:

1. **Export audit logs:**
   ```bash
   sqlite3 neolex.db ".dump" > incident-$(date +%Y%m%d)-audit-dump.sql
   ```

2. **Capture process state:**
   ```bash
   ps aux | grep neolex > incident-$(date +%Y%m%d)-process.txt
   netstat -an | grep 8000 >> incident-$(date +%Y%m%d)-process.txt
   ```

3. **Save application logs** (if log rotation is enabled, preserve current file)

Store evidence securely and document chain of custody.

---

## Communication Templates

### Client Notification (P1/P2)

```
Subject: Security Notice — [Service] — Action Required

Dear [Client Name],

We are writing to inform you of a security incident that may have affected
your NeoLex account.

What happened: [Brief description — when, what was accessed/exposed]
What we did: [Containment steps taken]
What you should do: [Rotate keys, review audit logs, etc.]

We take the security of your data seriously. Please contact [contact@example.com]
with any questions.

[Your name]
```

---

## Post-Incident Report Template

```
Incident ID: INC-YYYYMMDD-###
Date/Time: [UTC]
Severity: P1/P2/P3/P4
Reporter: [Name or source]

Timeline:
- [time]: Incident detected
- [time]: Investigation started
- [time]: Containment completed
- [time]: Recovery completed
- [time]: Clients notified (if required)

Root Cause:
[Description]

Impact:
- Data exposed: [yes/no, what]
- Clients affected: [list or "none"]
- Duration of exposure: [timeframe]

Remediation Taken:
1. [Action]
2. [Action]

Preventive Measures:
1. [Control to add]
2. [Process to change]

Lessons Learned:
[Key takeaways]
```
