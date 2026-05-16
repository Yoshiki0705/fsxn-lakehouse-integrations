# Directory Structure & Naming Conventions

## Top-Level Structure

```
fsxn-lakehouse-integrations/
├── README.md                    # Bilingual (JA/EN) project overview
├── docs/                        # Project-wide documentation
│   ├── ja/                      # Japanese documentation
│   ├── en/                      # English documentation
│   └── images/                  # Shared diagrams and images
├── shared/                      # Common modules (reused across integrations)
│   ├── cloudformation/          # Base CFn templates
│   ├── scripts/                 # Utility scripts (Python/Bash)
│   └── sample-data/             # Sample dataset definitions
├── integrations/                # Per-vendor implementations
│   └── <vendor>/                # One directory per platform
├── use-cases/                   # Industry-specific use cases
│   └── <industry-usecase>/      # One directory per use case
├── .github/workflows/           # CI/CD pipelines
├── .kiro/steering/              # Kiro steering files
├── package.json                 # Project metadata
└── jest.config.js               # Test configuration
```

## Integration Directory Standard (`integrations/<vendor>/`)

Each vendor integration MUST follow this structure:

```
integrations/<vendor>/
├── README.md                    # Integration overview (bilingual or link)
├── template.yaml                # CloudFormation template
├── terraform/                   # Terraform configs (if vendor requires)
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── providers.tf
├── notebooks/                   # Jupyter/Databricks notebooks
│   └── NN_description.py        # Numbered for execution order
├── sql/                         # SQL scripts (Snowflake/Athena/Trino)
│   └── NN_description.sql       # Numbered for execution order
├── docs/
│   ├── ja/                      # Japanese docs for this integration
│   │   └── setup-guide.md
│   └── en/                      # English docs for this integration
│       └── setup-guide.md
└── tests/                       # Integration-specific tests
    └── test_*.py
```

## Naming Conventions

### Files
- CloudFormation: `kebab-case.yaml` (e.g., `fsxn-s3ap-base.yaml`)
- Terraform: `snake_case.tf` (standard Terraform convention)
- Python scripts: `snake_case.py` (e.g., `validate_access.py`)
- Bash scripts: `kebab-case.sh` (e.g., `setup-s3ap.sh`)
- SQL scripts: `NN_snake_case.sql` (e.g., `01_storage_integration.sql`)
- Notebooks: `NN_snake_case.py` (e.g., `01_setup_external_location.py`)
- Documentation: `kebab-case.md` (e.g., `setup-guide.md`)

### Resources (CloudFormation/Terraform)
- CloudFormation Logical IDs: PascalCase (e.g., `FSxNFileSystem`, `S3AccessPoint`)
- CloudFormation Parameters: PascalCase (e.g., `EnvironmentName`, `VpcId`)
- Terraform resources: snake_case (e.g., `databricks_external_location`)
- S3 Access Point names: kebab-case (e.g., `fsxn-databricks-ap`)
- IAM Role names: kebab-case with environment prefix (e.g., `fsxn-lakehouse-databricks-role`)

### Tags
All AWS resources MUST include:
- `Name`: Human-readable name
- `Environment`: dev/staging/prod
- `Project`: fsxn-lakehouse-integrations
- `Integration`: vendor name (databricks/snowflake/etc.)

## Use Case Directory (`use-cases/<industry-usecase>/`)

```
use-cases/<industry-usecase>/
├── README.md                    # Use case overview
├── architecture.md              # Architecture specific to this use case
├── template.yaml                # CloudFormation (if applicable)
├── docs/
│   ├── ja/
│   └── en/
└── examples/                    # Code examples
```
