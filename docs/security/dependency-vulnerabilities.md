# NeoLex Dependency Vulnerability Status

**Last Scanned:** 2026-03-26
**Tool:** pip-audit 2.10.0
**Scope:** All installed Python packages in the conda/pip environment

---

## How to Re-run

```bash
# Install pip-audit if not present
pip install pip-audit

# Run full scan
bash scripts/audit-deps.sh

# Python packages only
bash scripts/audit-deps.sh --python-only
```

---

## Current Status

**Total findings:** 27 vulnerabilities in 14 packages

The findings below are categorized by whether they affect the NeoLex **runtime path**
(FastAPI server and arlc/ pipeline) or are in the broader research/ML environment only.

---

## NeoLex Runtime Path — Vulnerabilities

These packages are imported by the NeoLex FastAPI application or arlc/ pipeline.

| Package      | Version | CVE(s)                                         | CVSS   | Fix Version | Status            |
|--------------|---------|------------------------------------------------|--------|-------------|-------------------|
| aiohttp      | 3.13.2  | CVE-2025-69223 through CVE-2025-69230 (8 CVEs) | Medium | 3.13.3      | Patch next sprint |
| requests     | 2.32.5  | CVE-2026-25645                                 | Medium | 2.33.0      | Patch next sprint |
| urllib3      | 2.5.0   | CVE-2025-66418, CVE-2025-66471, CVE-2026-21441 | Medium | 2.6.3       | Patch next sprint |
| cryptography | 45.0.5  | CVE-2026-26007                                 | Medium | 46.0.5      | Patch next sprint |
| pyjwt        | 2.10.1  | CVE-2026-32597                                 | Medium | 2.12.0      | Patch next sprint |
| pypdf        | 6.9.1   | CVE-2026-33699                                 | Medium | 6.9.2       | Patch next sprint |
| pip          | 25.1    | CVE-2025-8869, CVE-2026-1703                   | Low    | 26.0+       | Non-blocking      |

**Assessment (2026-03-26):** No Critical (CVSS >= 9.0) vulnerabilities found in the
runtime path. All medium-severity issues are accepted for this sprint and scheduled for
patching in the next dependency update cycle. None of the CVEs in `aiohttp`, `requests`,
or `urllib3` have publicly available proof-of-concept exploits at the time of this audit.

---

## Research/ML Environment — Vulnerabilities

These packages are only used in benchmark scripts (`benchmarks/`) and are NOT part of
the deployed NeoLex application.

| Package   | Version | CVE(s)                                    | Fix Version | Notes                                   |
|-----------|---------|-------------------------------------------|-------------|-----------------------------------------|
| nltk      | 3.9.3   | GHSA-rf74, CVE-2026-33230, CVE-2026-33231 | 3.9.4       | Benchmark/research only                 |
| pillow    | 10.4.0  | CVE-2026-25990                            | 12.1.1      | Not imported by NeoLex API              |
| gradio    | 6.6.0   | CVE-2026-28414                            | 6.7.0       | Not imported by NeoLex API              |
| pyasn1    | 0.6.1   | CVE-2026-23490, CVE-2026-30922            | 0.6.3       | Transitive dep (via cryptography/oauth) |
| diskcache | 5.6.3   | CVE-2025-69872                            | n/a         | Benchmark/research only                 |
| pygments  | 2.19.1  | CVE-2026-4539                             | n/a         | Dev tooling only                        |
| wheel     | 0.45.1  | CVE-2026-24049                            | 0.46.2      | Build tool — not runtime                |

---

## Remediation Plan

### Sprint priority (patch now)

```bash
# Upgrade NeoLex runtime dependencies
pip install aiohttp>=3.13.3 requests>=2.33.0 urllib3>=2.6.3
pip install cryptography>=46.0.5 PyJWT>=2.12.0 pypdf>=6.9.2

# Re-run audit to verify
bash scripts/audit-deps.sh

# Run tests
python -m pytest tests/neolex/ -v
```

### Next sprint

```bash
# Upgrade research environment
pip install nltk>=3.9.4 pillow>=12.1.1 pyasn1>=0.6.3

# Upgrade build tools
pip install wheel>=0.46.2 pip>=26.0
```

---

## Accepted Risk Register

| CVE                     | Package   | Reason Accepted                               | Accepted By | Date       |
|-------------------------|-----------|-----------------------------------------------|-------------|------------|
| CVE-2025-69223 to 69230 | aiohttp   | No public PoC; medium severity; fix scheduled | Engineering | 2026-03-26 |
| CVE-2025-8869           | pip       | Build tool, not runtime                       | Engineering | 2026-03-26 |
| CVE-2026-1703           | pip       | Build tool, not runtime                       | Engineering | 2026-03-26 |
| CVE-2026-4539           | pygments  | Dev tooling, not in production deployment     | Engineering | 2026-03-26 |
| CVE-2026-24049          | wheel     | Build tool, not runtime                       | Engineering | 2026-03-26 |
| CVE-2025-69872          | diskcache | Benchmark/research only, not deployed         | Engineering | 2026-03-26 |

---

## Notes

- The scan covers the full conda environment, not just NeoLex's declared dependencies
  in `pyproject.toml`. Many findings are in unrelated ML/research tools.
- For a production deployment, consider using a dedicated virtual environment with
  only `pyproject.toml` dependencies to reduce the attack surface.
- `pip-audit` uses the PyPI Advisory Database (OSV). Cross-reference with
  NVD (https://nvd.nist.gov) for CVSS scores and additional context.
