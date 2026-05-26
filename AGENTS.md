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
