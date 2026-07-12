# AGENTS.md

> Data Lake and Lakehouse platform integrations with Amazon FSx for NetApp ONTAP via S3 Access Points

## Project Overview

This repository provides integration patterns for connecting Amazon FSx for NetApp ONTAP to AWS analytics services (Athena, Glue, EMR, SageMaker) via S3 Access Points.

## Build & Test Commands

```bash
# Install dependencies
npm install

# Run tests
npm test
```

## Coding Conventions

- Python 3.12 for Lambda functions
- TypeScript for CDK/infrastructure code
- Structured JSON logging
- Property-based tests with Hypothesis

## Supply-Chain Security

### Automated Security Workflows

| Workflow | File | Purpose |
|----------|------|---------|
| zizmor | `.github/workflows/zizmor.yml` | GitHub Actions security linting (SHA-pinning, credential persistence, injection) |
| gitleaks | `.github/workflows/gitleaks.yml` | Secret detection — custom rules in `.gitleaks.toml` |
| OpenSSF Scorecard | `.github/workflows/scorecard.yml` | Automated security health scoring |
| Renovate | `renovate.json` | Automated dependency updates ([Renovate GitHub App](https://github.com/apps/renovate) must be enabled on the repo) |

### Local Security Checks

```bash
# Pre-commit hook runs automatically on commit (via .githooks/pre-commit):
#   1. Author email verification
#   2. gitleaks secret scanning (staged files)
#   3. zizmor lint (if workflow files changed)

# Manual verification
gitleaks detect --config .gitleaks.toml --no-git --source .
zizmor .github/workflows/
```

### Actions Pinning Policy

- All third-party Actions MUST be pinned to SHA hashes: `uses: owner/action@<sha> # vX.Y.Z`
- `actions/checkout` must set `persist-credentials: false`
- Verify with `zizmor .github/workflows/` before committing workflow changes

### Custom Secret Detection (.gitleaks.toml)

Detects: internal IPs (10.x/172.16-31.x/192.168.x), AWS Account IDs, internal hostnames (`.internal.`/`.corp.`), VPN configs, NetApp internal references

## Agent Output Standards

> Mirror of the user-level Kiro global steering so any agent/contributor follows these even
> without that steering loaded. Enforced in CI by `.github/workflows/agent-output-audit.yml`
> (naming, neutrality, leak, JA/EN parity) and `.github/workflows/gitleaks.yml` (secrets).

### Naming (NetApp / AWS)

- Use **Amazon FSx for NetApp ONTAP** on first mention, then **FSx for ONTAP**. Never use
  `FSxN`, bare `FSx`, or `FSx ONTAP`. Use **FSx for ONTAP S3 AP** for the access point.
- Do **not** propose NetApp Workload Factory, NetApp Console, or BlueXP — reframe to native
  equivalents (CloudWatch, ONTAP REST API, FabricPool, AWS DataSync, Snapshot/FlexClone/SnapMirror).
- Exception: external citation titles quoted verbatim (mark the line with an `allow:naming` comment).

### Vendor neutrality (right-tool-for-the-job)

- No vendor-versus or superiority framing ("best", "beats X", "X より優れている", "競合ツール",
  "優位性", "game-changer"). Present alternatives as options and state trade-offs symmetrically,
  including the recommended option's own constraints.

### Public-output safety

- Never commit personal/persona names, emails, AWS account IDs, internal IPs/hostnames, support
  case numbers, or vendor-internal ticket IDs. Use role-based references ("Storage Specialist
  lens") and "an internal product request (tracked)".
- No process-metadata noise: do not add "Persona Review Summary" sections, review rounds, dates,
  or lens counts to published docs. Weave review findings as inline role-based lens notes
  (`> **Topic** (Role lens): ...`); keep provenance in `.private/` (gitignored).

### Bilingual docs (JA primary + EN)

- Keep JA/EN parity: matching section structure/count and equivalent inline notes. Mirror any
  add/restructure across both languages in the same change.

### Technical reference / guide docs

- Include: an executive-summary verdict, FAQ / common misconceptions, a selection flowchart
  (mermaid or ASCII), OT/IT security considerations (where relevant), phased adoption steps,
  a Related-Documents section with backlinks, and ≥10 inline role-based lens reviews.

### Before committing docs

```bash
gitleaks detect --config .gitleaks.toml --no-git --source .
# CI mirrors the agent-output checks; see .github/workflows/agent-output-audit.yml
```
