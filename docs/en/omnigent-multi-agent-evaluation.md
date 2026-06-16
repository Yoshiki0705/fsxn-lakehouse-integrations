🌐 **English** | [日本語](../ja/omnigent-multi-agent-evaluation.md)

# Omnigent Multi-Agent Integration: Evaluation for FSx for ONTAP Lakehouse Workflows

> **Status**: Phase 0 evaluation complete (installation verified, basic operation confirmed). Alpha software — API stability not guaranteed. Updated 2026-06-15.

> **Review note**: This evaluation was produced through a multi-lens architecture review. Reviewer lenses are described by **role only** (no individual or employer attribution). Each claim is tagged by evidence tier: **Public** (verifiable from public sources), **Archetype** (generic role-based reasoning), **Project-context** (internal validation).

---

## What Is Omnigent

Omnigent is an open-source (Apache 2.0) **meta-harness** open-sourced by Databricks (announced by co-founder Matei Zaharia) in mid-June 2026. It provides a unified interface to compose, govern, and collaborate on AI agent sessions across multiple harnesses (Claude Code, Codex, Pi, custom agents).

| Capability | Description |
|-----------|-------------|
| Composition | Combine multiple models and harnesses without rewriting code |
| Contextual Policies | Stateful cost caps, model routing, risk-based escalation — enforced at runtime, not via prompts |
| Secure OS Sandbox (Omnibox) | Restrict filesystem/network access, hide credentials from agents |
| Collaboration | Share live sessions via URL for real-time team co-piloting |
| Built-in Agents | Polly (multi-agent coding orchestrator) and Debby (model debate) |
| Multi-device | Terminal, Web UI, Desktop, Mobile, REST API |
| Custom Agents | Declarative YAML definition with MCP tool support |

**Sources**: [Databricks Blog](https://www.databricks.com/blog/introducing-omnigent-meta-harness-combine-control-and-share-your-agents) | [omnigent.ai](https://omnigent.ai/) | [GitHub](https://github.com/omnigent-ai/omnigent)

### DAIS 2026 Update (2026-06-16): Managed Omnigent + Unity AI Gateway

At Data + AI Summit 2026, Databricks announced two developments that directly affect this evaluation (evidence tier: **Public**):

- **Managed Omnigent on Databricks (Beta)**: the same open-source Omnigent, deployable to Databricks as managed workflows with shared history, remote access, collaboration, and isolated cloud execution on **Lakebox**. Existing setups, harnesses, workflows, and skills run without rebuilding. ([AI Gateway announcement](https://www.databricks.com/blog/ai-governance-data-ai-summit-2026-whats-new-unity-ai-gateway))
- **Unity AI Gateway**: a Unity Catalog–based governance layer that governs models, agents, MCP services, and skills, and **governs every Managed Omnigent interaction** with centrally defined policies, cost controls (hard spend caps, smart routing), runtime Contextual Service Policies (Beta: allow / deny / require-approval), built-in guardrails (PII, prompt injection, jailbreaks, unsafe content), and unified agent tracing (analyzed in Lakewatch). ([What's new in Unity Catalog](https://www.databricks.com/blog/whats-new-unity-catalog-data-ai-summit-2026))

**Implication for this evaluation**: the "development = Omnigent / production = Databricks" hypothesis is now concrete. Self-hosted OSS Omnigent suits development and multi-vendor experimentation; **Managed Omnigent on Databricks governed by Unity AI Gateway** is the production path for the same workflows. This is reflected in the comparison and design sections below.

---

## Why This Matters for FSx for ONTAP Lakehouse Integrations

This repository validates integration patterns between FSx for ONTAP and analytics platforms. Omnigent is relevant at three levels:

### 1. Development Workflow Enhancement

Omnigent can orchestrate multiple coding agents working in parallel on this repository's PoC templates, integration tests, and documentation — governed by cost policies and sandboxed to specific directories.

### 2. Manufacturing Data Platform — Multi-Agent Quality Pipeline

The [manufacturing data platform PoC](../../integrations/manufacturing-data-platform/) involves Kafka, ClickHouse, FSx for ONTAP, and Databricks. Omnigent's supervisor-agent pattern enables:
- Dedicated sub-agents for schema validation, anomaly detection, and payload cataloging
- ClickHouse read-only policies enforced at the meta-harness layer
- Cost caps and escalation thresholds for AI-powered quality inspection

### 3. Iceberg Metadata Catalog — Multi-Model Classification

The [Iceberg metadata catalog](../../integrations/iceberg-metadata-catalog/) uses Bedrock Vision for file classification. Omnigent's Debby (model debate) pattern enables multi-model comparison to improve classification confidence.

---

## Phase 0 Evaluation Results (2026-06-15)

### Installation

| Environment | Result | Notes |
|-------------|--------|-------|
| macOS (Intel x86_64) | ❌ Not supported | `cel-expr-python` dependency lacks x86_64 macOS wheel |
| Ubuntu 24.04 (x86_64 Linux) | ✅ Success | Omnigent 0.1.0, all CLI commands functional |
| macOS (Apple Silicon ARM64) | ✅ Expected to work | Wheel available but not tested in this project |

### System Requirements

- Python 3.12+
- Node.js 22 LTS + npm
- tmux
- uv (Python package manager)

### Verified Capabilities (Project-context)

| Capability | Verified | Method |
|-----------|:---:|--------|
| CLI installation | ✅ | `curl -fsSL https://omnigent.ai/install.sh \| sh` |
| Server startup | ✅ | `omnigent server start` → http://127.0.0.1:6767 |
| REST API `/v1/agents` | ✅ | Returns 4 built-in agents (debby, polly, claude-native-ui, codex-native-ui) |
| REST API `/v1/policies` | ✅ | Empty list (no policies configured) — confirms API operational |
| Web UI | ✅ | SPA served at server root |
| MCP tool support | ✅ (documented) | stdio and HTTP transports, bundled servers (GitHub, Slack, etc.) |
| Databricks FMAPI integration | ✅ (documented) | `databricks-` model prefix, `~/.databrickscfg` profile auth |

### Key Architecture Findings

```
Interfaces (Terminal / Web / Desktop / Mobile / REST API)
    ↓
Server (Policies + Session Store + REST API, port 6767)
    ↓
Runner (Sandboxed agent execution — local, Modal, or Daytona)
    ↓
Agent (Harness + Model + Tools + Policies, defined in YAML)
```

- **Server is stateful**: SQLite (or Postgres) for session persistence and policy state
- **Policies are dynamic**: Track cumulative cost, tool call count, risk score across a session
- **Three policy levels**: Session (user) > Agent config (developer) > Server-wide (admin)
- **Sub-agents as tools**: One agent can delegate to others via `type: agent` tool definition

---

## Design: Integration with Kiro AIDLC

### Complementary Model

| Layer | Tool | Responsibility |
|-------|------|---------------|
| Design & Lifecycle | Kiro | Spec (requirements → design → tasks), Steering, Hooks |
| Runtime Composition | Omnigent | Multi-agent orchestration, policies, sandboxing, collaboration |
| Production governance | Unity AI Gateway | Runtime policy enforcement, hard spend caps, guardrails, agent tracing for models/agents/MCP/skills |
| Production Pipelines | Databricks Agent Bricks / Lakeflow | Unity Catalog governance, managed deployment |

Kiro and Omnigent do not overlap. Kiro manages **what to build** (spec-driven). Omnigent manages **how to run agents together** (runtime composition). Production data pipelines use Databricks Workflows / DLT for orchestration — Omnigent is not used for pipeline scheduling.

### Policy Responsibility Split

| Control | Kiro | Omnigent |
|---------|------|----------|
| Code quality (lint, format) | ✅ Hooks (fileEdited) | — |
| Security (secrets, Actions) | ✅ pre-commit + CI | — |
| LLM cost control | — | ✅ cost_budget policy |
| File access restriction | — | ✅ Omnibox sandbox |
| Data access (FSx ACL) | Steering (principles) | Custom policy (enforcement) |
| Multi-agent review | — | ✅ Polly cross-review |

### Bedrock Integration Path

Omnigent does not natively support Amazon Bedrock as a model provider. Three paths are available:

1. **Databricks Foundation Model API** (primary): Route Bedrock models through Databricks workspace
2. **OpenAI-compatible Gateway** (fallback): Use LiteLLM or similar proxy
3. **MCP Tool** (for Bedrock-specific APIs): Vision classification, embeddings as tool calls

---

## Use Case Designs

### Manufacturing Quality Supervisor (Multi-Agent)

```
Supervisor Agent (Claude Sonnet)
  ├─→ anomaly-detector (ClickHouse readonly queries)
  ├─→ quality-reporter (structured JSON reports)
  └─→ payload-cataloger (FSx for ONTAP → Iceberg)

Policies:
  - daily_cost_cap: $10/day
  - rate_limit: 200 tool calls/session
  - clickhouse: SELECT only (INSERT/UPDATE/DELETE denied)
  - fsxn: deny-by-default, read-only via NFS mount

Design decisions:
  - Real-time detection: ClickHouse Materialized Views (non-AI, sub-second)
  - Batch analysis: Omnigent agents (AI-powered, seconds to minutes)
  - Agents do NOT replace ClickHouse rule-based alerting
```

### Iceberg Multi-Model Classifier (Debby Pattern)

```
Classifier Orchestrator
  → Run same image through 3 models (Claude Haiku / Titan / Nova)
  → Compare results (Debby debate pattern)
  → Majority vote → accept
  → Disagreement → escalate to human review
  → Record results to Iceberg table (UC lineage preserved)

Target: +5% F1 score improvement over single-model baseline
```

---

## FSx for ONTAP Integration Design

### Multi-Protocol Access Pattern

| Use Case | Protocol | Rationale |
|----------|----------|-----------|
| Image/video payload read | NFS mount (`/mnt/fsxn/`) | Low latency, POSIX ACL |
| Parquet for analytics | S3 Access Point | Consistency with Athena/EMR/Databricks |
| Metadata catalog operations | S3 Access Point | Iceberg table writes |
| Quality report output | NFS mount | File-based output |

### Data Protection Integration

| ONTAP Feature | Agent Use Case |
|--------------|---------------|
| Snapshot | Consistent point-in-time data for batch analysis |
| FlexClone | A/B testing with identical datasets (zero-copy) |
| SnapMirror | DR for agent-generated metadata |
| FPolicy audit | Correlate agent access logs with ONTAP audit events |

### Security Design

- **Deny-by-default**: Agents cannot access files unless explicitly allowed
- **Omnibox sandbox**: `read_paths` restricted to designated FSx volumes
- **No credential exposure**: API keys brokered through Omnigent, never visible to agent
- **Audit trail**: Agent tool calls logged + ONTAP fpolicy events for correlation
- **Prompt injection defense**: Retrieved file content treated as data, not instructions

---

## Observability Design

| Metric | Purpose | Alert Threshold |
|--------|---------|----------------|
| `omnigent.session.cost_usd` | Cumulative LLM cost | > $5/session |
| `omnigent.agent.tool_calls` | Tool call count | > 100/session |
| `omnigent.policy.deny_count` | Policy denials | > 10/hour |
| `omnigent.agent.latency_ms` | Response time | P99 > 30s |

Integration: Omnigent OpenTelemetry → AWS Distro for OpenTelemetry (ADOT) → CloudWatch Metrics + X-Ray.

---

## Comparison: Omnigent vs Databricks Agent Bricks

| Dimension | Omnigent (OSS, self-hosted) | Managed Omnigent on Databricks | Agent Bricks Supervisor Agent |
|-----------|----------------------------|-------------------------------|-------------------------------|
| Management | Self-hosted (OSS) | Databricks managed (Beta, runs on Lakebox) | Databricks managed (GA) |
| Governance | Custom policies (CEL) | Unity AI Gateway (UC-native runtime policies) | Unity Catalog (native) |
| Model support | Multi-vendor | Multi-vendor + smart routing via AI Gateway | Databricks FMAPI-centric |
| Collaboration | URL session sharing | Shared history + remote access | Within Databricks Apps |
| Deployment | EC2 / ECS / Modal | Lakebox (isolated cloud execution) | Databricks Apps |
| Sandbox | OS-level (Omnibox) | Lakebox isolation | Compute isolation |
| Best for | Development, experimentation, cross-vendor | Production agent workflows alongside UC data | Production enterprise agent orchestration |

**Unity AI Gateway** is the governance layer common to the managed paths: it governs models, agents, MCP services (managed connectors for Google Drive, Jira, Confluence, Slack, GitHub, SharePoint, plus custom), and skills with hard spend caps, smart routing, Contextual Service Policies (Beta), guardrails, and unified tracing.

**Selection guidance** (Archetype reasoning):
- Use **OSS Omnigent** for: multi-vendor model experiments, development-time orchestration, session-sharing collaboration, environments outside Databricks
- Use **Managed Omnigent on Databricks** for: running the same workflows in production under Unity AI Gateway governance, alongside UC-governed data
- Use **Agent Bricks** for: production enterprise agent orchestration with managed SLA built natively on UC

---

## Guardrail Architecture (Three Layers)

```
Layer 1: Omnigent Policies — runtime control (cost, rate, ACL)
Layer 2: Bedrock Guardrails — model output filtering (PII, toxicity, off-topic)
Layer 3: Application Validation — schema + business logic checks
```

Each layer operates independently. If any layer returns DENY, the output is blocked.

---

## Limitations and Constraints

| Constraint | Impact | Mitigation |
|-----------|--------|------------|
| Alpha status | API may change | Pin version, keep YAML minimal |
| No macOS Intel support | Cannot develop on older Macs | Use Linux (EC2/Docker) or Apple Silicon |
| No native Bedrock provider | Cannot use Bedrock directly as model | Gateway or Databricks FMAPI routing |
| Single-server architecture | SPOF in production | systemd/ECS auto-restart (PoC); or use Managed Omnigent on Databricks (Lakebox) for production |
| Credential vending not yet for Volumes | Cannot share unstructured data via OpenSharing connector | Track connector development, use NFS/S3 AP directly |

---

## Next Steps

| Phase | Activity | Timeline |
|-------|----------|----------|
| 0 | ✅ Installation + evaluation | Complete |
| 1 | Kiro Steering integration guide | 2026-06 |
| 2 | Iceberg Multi-Model Debate PoC | 2026-07 |
| 3 | Manufacturing Multi-Agent Quality design | 2026-07 |
| 4 | Public documentation finalization | 2026-07 |

---

## References

- [Omnigent Official Site](https://omnigent.ai/)
- [Omnigent GitHub Repository](https://github.com/omnigent-ai/omnigent)
- [Databricks Blog: Introducing Omnigent](https://www.databricks.com/blog/introducing-omnigent-meta-harness-combine-control-and-share-your-agents)
- [Unity AI Gateway (DAIS 2026)](https://www.databricks.com/blog/ai-governance-data-ai-summit-2026-whats-new-unity-ai-gateway) — Managed Omnigent on Databricks + AI governance
- [What's new with Unity Catalog (DAIS 2026)](https://www.databricks.com/blog/whats-new-unity-catalog-data-ai-summit-2026)
- [Agent Bricks Supervisor Agent GA](https://www.databricks.com/blog/agent-bricks-supervisor-agent-now-ga-orchestrate-enterprise-agents)
- [Omnigent Docs: Custom Agents](https://omnigent.ai/docs/use/custom-agents)
- [Omnigent Docs: Contextual Policies](https://omnigent.ai/docs/policies/overview)
- [Omnigent Docs: MCP & Tools](https://omnigent.ai/docs/build/tools)
