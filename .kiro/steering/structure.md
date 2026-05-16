---
inclusion: auto
---

# Directory Structure & Naming Conventions

## Top-Level Structure

```
fsxn-lakehouse-integrations/
├── README.md                    # Bilingual project overview
├── tasks.md                     # E2E verification tasks (bilingual)
├── docs/                        # Project-wide documentation
│   ├── ja/                      # Japanese docs
│   ├── en/                      # English docs
│   └── images/                  # Shared diagrams
├── shared/                      # Common modules
│   ├── cloudformation/          # Base CFn templates
│   ├── scripts/                 # Utility scripts
│   └── sample-data/             # Sample datasets
├── integrations/                # Per-vendor implementations
│   └── <vendor>/                # Standard structure (see below)
├── use-cases/                   # Industry use cases
├── .github/workflows/           # CI/CD
├── package.json                 # Project metadata
└── .gitignore                   # Excludes .kiro/, secrets, env files
```

## Integration Directory Standard

```
integrations/<vendor>/
├── README.md                    # Bilingual overview with language switcher
├── template.yaml                # CloudFormation template
├── terraform/                   # Terraform (if vendor requires)
├── notebooks/                   # Numbered: NN_description.py
├── sql/                         # Numbered: NN_description.sql
├── docs/
│   ├── ja/                      # Japanese docs
│   └── en/                      # English docs
└── tests/
    ├── test_*.py                # Automated tests
    ├── results/                 # Generated test results (gitignored)
    └── screenshots/             # Captured screenshots (gitignored)
```

## Naming Conventions

- CloudFormation: `kebab-case.yaml`
- Terraform: `snake_case.tf`
- Python: `snake_case.py`
- Bash: `kebab-case.sh`
- SQL: `NN_snake_case.sql`
- Notebooks: `NN_snake_case.py`
- Docs: `kebab-case.md`

## What Goes in .gitignore

### Excluded from repo:
- `.kiro/` — IDE-specific configuration
- `*.env`, `env.yaml` — Environment variables with real values
- `*.tfvars` (except examples) — Terraform variables with real values
- `*-params.json` — CloudFormation parameters with real values
- `*.pem`, `*.key` — Secrets and keys
- `**/tests/results/` — Generated test results
- `**/tests/screenshots/` — Captured screenshots
- `.terraform/`, `*.tfstate` — Terraform state

### Included in repo:
- `*.tfvars.example` — Example variable files (with placeholder values)
- `*-params.example.json` — Example parameter files
- All templates, scripts, docs, notebooks
