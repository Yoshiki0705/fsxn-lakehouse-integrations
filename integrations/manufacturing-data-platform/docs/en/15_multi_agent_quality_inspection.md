🌐 **English** | [日本語](../ja/15_multi_agent_quality_inspection.md)

# Multi-Agent Quality Inspection with Omnigent

> **Status**: Design phase. Depends on Manufacturing PoC Phase A infrastructure completion.
> **Last updated**: 2026-06-15
> **Related**: [Architecture Design](03_architecture_design.md) | [Realtime Analytics Landscape](14_realtime_analytics_landscape.md)

---

## Overview

This document describes the design for an AI-powered multi-agent quality inspection system built on Omnigent, integrated with the manufacturing data platform's Kafka + ClickHouse + FSx for ONTAP + Databricks architecture.

**Key design decision**: Real-time detection remains the responsibility of ClickHouse Materialized Views (rule-based, sub-second). Omnigent agents handle **batch quality analysis**, **trend detection**, **report generation**, and **AI-powered anomaly classification** (seconds to minutes).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Edge / Factory                                                  │
│  Sensors → MQTT → Kafka (MSK) → Topics:                         │
│    • mfg.sensors.temperature                                     │
│    • mfg.sensors.vibration                                       │
│    • mfg.quality.inspection-logs                                 │
│    • mfg.payloads.new-file-events                                │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Real-Time Layer (ClickHouse)                                    │
│  • Kafka Engine (sub-second ingestion)                           │
│  • Materialized Views (rule-based anomaly detection)             │
│  • Alerts (threshold-based, instant)                             │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ (triggered by alert OR scheduled)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  AI Quality Layer (Omnigent)                                     │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Supervisor Agent                                         │    │
│  │  ├─→ anomaly-detector (ClickHouse MCP, read-only)        │    │
│  │  ├─→ quality-reporter (structured JSON output)           │    │
│  │  └─→ payload-cataloger (FSx for ONTAP → Iceberg)        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Policies: cost_cap=$10/day, ClickHouse=SELECT only,            │
│            FSx=deny-by-default, escalation=score>0.8            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Governance Layer (Databricks)                                   │
│  • Unity Catalog (lineage, ACL, audit)                           │
│  • Delta Lake (quality results table)                            │
│  • MLflow (model evaluation tracking)                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agent Design

### Supervisor Agent

Orchestrates the quality inspection workflow. Delegates specialized tasks to sub-agents.

**Responsibilities**:
- Receive trigger (schedule or alert)
- Query ClickHouse for recent anomaly patterns
- Delegate analysis to sub-agents
- Aggregate findings
- Escalate critical issues (anomaly_score > 0.8)
- Write results to Databricks UC managed table

### Sub-Agent: Anomaly Detector

**Purpose**: Query ClickHouse time-series data to identify patterns

**Constraints**:
- Read-only SQL (SELECT, SHOW, DESCRIBE, EXPLAIN)
- Query timeout: 10 seconds
- Max result rows: 10,000
- Parameterized queries (SQL injection prevention)
- Must report `data_as_of` timestamp

### Sub-Agent: Quality Reporter

**Purpose**: Generate structured quality reports from inspection findings

**Output format**:
```json
{
  "report_id": "uuid",
  "data_as_of": "2026-06-15T12:00:00Z",
  "data_staleness_seconds": 45,
  "findings": [
    {
      "finding_id": "uuid",
      "category": "temperature_anomaly",
      "severity": "high",
      "confidence": 0.92,
      "evidence": "Sensor S-101 exceeded 85°C for 5 consecutive readings",
      "recommendation": "Schedule maintenance inspection within 24h",
      "source_query": "SELECT ... FROM sensor_readings WHERE ..."
    }
  ],
  "summary": {
    "total_findings": 3,
    "critical": 1,
    "high": 1,
    "medium": 1,
    "escalated": true
  }
}
```

### Sub-Agent: Payload Cataloger

**Purpose**: Register new quality inspection images/videos from FSx for ONTAP into Iceberg metadata catalog

**Constraints**:
- FSx for ONTAP read-only via NFS mount
- Writes metadata to Iceberg table (S3 Access Point)
- Links payload URI to quality event in ClickHouse

---

## Data Isolation (Factory/Line Level)

Each factory line operates within its own data boundary:

```yaml
# Line A agent instance
os_env:
  sandbox:
    read_paths: [/mnt/fsxn/factory-tokyo/line-a/]
    write_paths: [./output/line-a/]

# Line B agent instance
os_env:
  sandbox:
    read_paths: [/mnt/fsxn/factory-tokyo/line-b/]
    write_paths: [./output/line-b/]
```

Agents for Line A cannot access Line B data. This is enforced at the OS sandbox level (Omnibox), not via prompts.

---

## Resilience Design

| Failure Mode | Agent Behavior | Recovery |
|-------------|---------------|----------|
| Kafka no messages > 5 min | Log WARNING, report data_staleness | Continue monitoring |
| ClickHouse query timeout > 10s | Retry once, then skip with ERROR | Log to DLQ equivalent |
| FSx for ONTAP mount unreachable | STOP immediately, escalate | Require human restart |
| Omnigent server crash | Sessions persist in DB | systemd auto-restart |
| Cost budget exceeded | Session paused (ASK policy) | Human approval to continue |

---

## Integration with Existing PoC Infrastructure

| Component | Status | Connection to Multi-Agent |
|-----------|--------|--------------------------|
| MSK (Kafka) | Phase A ✅ | Agent triggered by topic events |
| ClickHouse Cloud | Phase A ✅ | Sub-agent queries via MCP |
| FSx for ONTAP volumes | Phase A ✅ | Payload storage, NFS mount |
| Databricks workspace | Phase A 🔄 | UC table for results, FMAPI for models |

---

## Observability

| Metric | Source | Alert |
|--------|--------|-------|
| `quality.findings.critical` | Agent output | > 0 → PagerDuty |
| `quality.data_staleness_seconds` | Agent output | > 300 → WARNING |
| `omnigent.session.cost_usd` | Omnigent telemetry | > $5/session |
| `clickhouse.query_duration_ms` | ClickHouse MCP | P99 > 5000ms |

---

## Cost Estimate

| Component | Unit Cost | Monthly (10 inspections/day) |
|-----------|-----------|------------------------------|
| Supervisor Agent (Claude Sonnet) | ~$0.05/inspection | ~$15 |
| Anomaly Detector queries | ~$0.01/inspection | ~$3 |
| Quality Reporter (Haiku) | ~$0.005/inspection | ~$1.5 |
| Payload Cataloger (embeddings) | ~$0.01/file | Variable |
| **Total** | | **~$20-50/month** |

Governed by `daily_cost_cap: $10` policy.

---

## Prerequisites

- [ ] Manufacturing PoC Phase A infrastructure complete
- [ ] Omnigent installed on EC2 (Ubuntu 24.04, verified)
- [ ] Anthropic API key configured (`omnigent setup`)
- [ ] ClickHouse MCP server implemented
- [ ] FSx for ONTAP NFS mount accessible from agent host
- [ ] Databricks workspace with FMAPI access

---

## References

- [Omnigent Multi-Agent Evaluation](../../../../docs/en/omnigent-multi-agent-evaluation.md)
- [Architecture Design](03_architecture_design.md)
- [Realtime Analytics Landscape](14_realtime_analytics_landscape.md)
- [SLO & Operational Readiness](10_slo_operational_readiness.md)
