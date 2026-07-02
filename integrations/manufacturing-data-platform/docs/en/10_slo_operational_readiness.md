# SLO and Operational Readiness

🌐 **English** | [日本語](../ja/10_slo_operational_readiness.md)

---

> Addresses P0 items from SA Persona Review Board (Persona 6: Reliability/Operations Reviewer).
> Defines Service Level Objectives, operational ownership, dependency failure modes, and runbook index.

---

## SLO-001: Service Level Objectives

### PoC SLO Table

| SLO ID | Service Level Objective | Target | Measurement Method | Degraded Threshold | Alert |
|--------|------------------------|--------|-------------------|-------------------|-------|
| SLO-01 | Event ingestion availability | 99.9% uptime | % of time MSK accepts producer writes (5-min windows) | < 99% over 1 hour | Critical |
| SLO-02 | Kafka → ClickHouse freshness | < 5 seconds | `now() - max(timestamp)` in ClickHouse vs Kafka latest offset | > 30 seconds | Warning; > 5 min = Critical |
| SLO-03 | Kafka → Databricks freshness | < 5 minutes | Kafka consumer lag (latest offset − committed offset) × avg msg interval | > 15 minutes | Warning; > 1 hour = Critical |
| SLO-04 | ClickHouse query availability | 99.5% | % of successful queries (HTTP 200) / total queries (5-min windows) | < 95% over 15 min | Critical |
| SLO-05 | ClickHouse query latency (P99) | < 2 seconds | P99 of SELECT query duration on factory.sensor_data | > 5 seconds | Warning |
| SLO-06 | Payload availability | 99.9% | % of payload_uri in Delta tables resolvable to actual files | < 99% (sample check) | Critical |
| SLO-07 | Data loss (events) | 0 events lost | Periodic reconciliation: Kafka offset count vs ClickHouse row count vs Delta row count | Any delta > 0 (beyond pipeline lag) | Critical |
| SLO-08 | Edge buffer queue depth | < 1M events | Store-and-forward SQLite queue size | > 5M events | Warning; > 8 GB = Critical |
| SLO-09 | Payload upload success rate | > 99% | Successful uploads / attempted uploads (per hour) | < 95% | Warning; < 90% = Critical |
| SLO-10 | FlexCache hit ratio (Phase B) | > 80% | Cache hits / (cache hits + cache misses) | < 50% over 1 hour | Warning (cache sizing review) |

### Production SLO Targets (Future Reference)

| SLO | PoC Target | Production Target | Delta |
|-----|-----------|------------------|-------|
| Event ingestion | 99.9% | 99.95% | Multi-AZ MSK, Instaclustr HA |
| Kafka→ClickHouse freshness | < 5s | < 2s | Tuned consumers, larger instances |
| Kafka→Databricks freshness | < 5 min | < 1 min | Continuous trigger, higher DBU |
| Query availability | 99.5% | 99.9% | HA ClickHouse (3+ replicas) |
| Data loss | 0 | 0 | Same (non-negotiable) |

---

## SLO-002: Operational Ownership

### RACI Matrix

| Component | Responsible (operates) | Accountable (owns) | Consulted | Informed |
|-----------|----------------------|--------------------|-----------|---------| 
| Amazon MSK | Platform Engineer | Architecture Lead | AWS Support | Team |
| ClickHouse (Cloud) | ClickHouse SRE (managed) | Architecture Lead | ClickHouse Support | Team |
| ClickHouse (Instaclustr, Phase B) | Instaclustr SRE | Architecture Lead | Instaclustr SE | Team |
| FSx for ONTAP | Platform Engineer | Architecture Lead | AWS Support / NetApp | Team |
| Databricks workspace | Data Engineer | Architecture Lead | Databricks Support | Team |
| Streaming pipelines | Data Engineer | Architecture Lead | — | Team |
| Edge devices (Phase B) | Edge Engineer | Architecture Lead | — | Team |
| VPC / Networking | Platform Engineer | Architecture Lead | AWS Support | Team |
| Unity Catalog governance | Data Engineer | Architecture Lead | Databricks Support | Team |

### On-Call / Escalation (PoC Phase)

| Severity | Response Time | Escalation Path |
|----------|-------------|-----------------|
| Critical (data loss, full outage) | 30 minutes | Architecture Lead → AWS/vendor support |
| Warning (degraded, high latency) | 4 hours | Assigned owner → Architecture Lead if unresolved |
| Informational | Next business day | Log and review in weekly sync |

> Note: During PoC, "on-call" is best-effort during business hours. No 24/7 coverage expected.

---

## SLO-003: Dependency Failure Mode Analysis

### Component Failure Modes

| Component | Failure Mode | Blast Radius | Detection | Auto-Recovery | Manual Recovery |
|-----------|-------------|-------------|-----------|--------------|-----------------|
| **MSK** | Broker unavailable | Edge buffer fills; ClickHouse/Databricks starved | Producer delivery errors; consumer lag spike | MSK Multi-AZ failover (< 30s) | None needed if Multi-AZ |
| **MSK** | Topic deletion (accidental) | Complete data path broken | Consumer errors; no new data | None | Recreate topic; replay from edge buffer |
| **ClickHouse** | Service down | Real-time dashboards unavailable | Query errors; health check fails | ClickHouse Cloud auto-restart | Manual restart if self-managed |
| **ClickHouse** | Kafka consumer lag | Dashboard shows stale data | Lag metric > threshold | Auto-catch-up on recovery | Increase consumers if sustained |
| **FSx for ONTAP** | Volume full | Payload uploads fail; dead-letter queue fills | CloudWatch StorageCapacity alarm | None (provisioned) | Add capacity or clean up |
| **FSx for ONTAP** | NFS mount unreachable | Payload uploads fail; edge buffer grows | Upload error count; mount health | Reconnect on network recovery | Check security groups, DNS |
| **Databricks** | Streaming job fails | Delta tables not updated; Kafka lag grows | Job status API; consumer lag | Job retry policy (3 attempts) | Manual restart; checkpoint recovery |
| **Databricks** | Workspace unreachable | No streaming or analytics | API health check | Databricks platform recovery | Wait for platform; jobs resume from checkpoint |
| **VPN/DX (Phase B)** | Connectivity lost | FlexCache misses fail; Kafka replication stops | VPN tunnel status; replication lag | VPN auto-reconnect | Manual tunnel re-establishment |
| **Edge device** | Device crash | Events lost in Kafka producer buffer | Heartbeat missing | Device auto-restart (systemd) | Replace hardware if persistent |
| **Edge network** | Factory LAN down | All edge events buffered locally | Queue depth grows; no new Kafka messages | Auto-resume on network recovery | Investigate factory network |

### Cascading Failure Scenarios

| Scenario | Chain | Final Impact | Mitigation |
|----------|-------|-------------|-----------|
| Factory network outage | Edge devices → buffer fills → Kafka starved → ClickHouse/Databricks stale | Dashboards show old data; no new Delta rows | Edge buffer (10 GB); accept staleness; alert on lag |
| MSK cluster failure | Kafka unavailable → ClickHouse stops ingesting → Databricks stops streaming | All downstream stale | MSK Multi-AZ; edge buffer holds events |
| FSx for ONTAP full | Uploads fail → dead-letter → no new payloads → Delta tables have NULL payload_uri | Analytics on events continues; payload access broken | Capacity alarm at 80%; auto-tier cold data |
| ClickHouse + Databricks both down | Only Kafka and FSx running | No analytics available; data still safe in Kafka + ONTAP | Accept temporary analytics blackout; data preserved |

---

## SLO-004: Monitoring and Alerting Configuration

### CloudWatch Alarms (AWS Components)

| Alarm | Metric | Threshold | Period | Action |
|-------|--------|-----------|--------|--------|
| MSK Consumer Lag (ClickHouse) | `kafka.consumer_group.lag` | > 10,000 messages | 5 min | Warning → SNS |
| MSK Consumer Lag (Databricks) | `kafka.consumer_group.lag` | > 100,000 messages | 5 min | Warning → SNS |
| FSx Storage Capacity | `StorageCapacity` (used %) | > 80% | 15 min | Critical → SNS |
| FSx Throughput | `DataReadBytes` + `DataWriteBytes` | > 90% of provisioned | 5 min | Warning → SNS |
| VPC Endpoint Health | `VPCEndpoint.PacketsDropped` | > 0 | 5 min | Warning → SNS |

### ClickHouse Monitoring

| Metric | Source | Threshold | Alert |
|--------|--------|-----------|-------|
| Query duration P99 | `system.query_log` | > 2 seconds | Warning |
| Kafka consumer lag | `system.kafka_consumers` | > 5,000 messages | Warning |
| Insert rate | `system.events` (InsertedRows) | Drop > 50% from baseline | Warning |
| Merges behind | `system.merges` (active count) | > 50 concurrent | Warning |

### Databricks Monitoring

| Metric | Source | Threshold | Alert |
|--------|--------|-----------|-------|
| Streaming batch duration | Spark UI / metrics | > 60 seconds per batch | Warning |
| Records processed per batch | StreamingQueryListener | Drop to 0 for > 5 minutes | Critical |
| Checkpoint lag | Custom metric (Kafka offset − checkpoint offset) | > 100,000 | Warning |
| Job state | Jobs API | state != RUNNING | Critical |

### Edge Device Monitoring (Phase B)

| Metric | Source | Threshold | Alert |
|--------|--------|-----------|-------|
| Queue depth | SQLite row count (exported via MQTT) | > 1M events | Warning |
| Last successful delivery | Timestamp of last Kafka ack | > 10 minutes ago | Warning |
| Payload upload failures | Counter (dead-letter directory file count) | > 0 | Critical |
| Device heartbeat | MQTT will/testament | Missing for > 5 minutes | Critical |

---

## SLO-005: Runbook Index

### Runbook Structure

Each runbook follows this template:

```
## RUN-XXX: <Title>
- Trigger: What alarm/condition triggers this
- Impact: What is broken and who is affected
- Steps: 1, 2, 3... diagnostic and recovery
- Verification: How to confirm recovery
- Escalation: When to escalate and to whom
- Prevention: How to prevent recurrence
```

### Runbook Registry

| ID | Title | Trigger | Priority |
|----|-------|---------|----------|
| RUN-001 | MSK Consumer Lag Resolution | Consumer lag > 10K for ClickHouse | P1 |
| RUN-002 | Databricks Streaming Job Recovery | Job state != RUNNING for > 5 min | P0 |
| RUN-003 | FSx for ONTAP Storage Full | StorageCapacity > 80% | P1 |
| RUN-004 | Edge Buffer Overflow | Queue depth > 5M events | P1 |
| RUN-005 | Payload Upload Failure | Dead-letter count > 0 | P0 |
| RUN-006 | ClickHouse Query Timeout | P99 > 5 seconds sustained | P1 |
| RUN-007 | FlexCache Miss Rate High (Phase B) | Hit ratio < 50% for > 1 hour | P2 |
| RUN-008 | Kafka Replication Lag (Phase B) | MirrorMaker lag > 1 hour | P1 |
| RUN-009 | Data Reconciliation Mismatch | Kafka offsets ≠ ClickHouse + Delta counts | P0 |
| RUN-010 | Edge Device Heartbeat Lost | No heartbeat for > 5 min | P1 |

### Sample Runbook: RUN-002 — Databricks Streaming Job Recovery

```
## RUN-002: Databricks Streaming Job Recovery

### Trigger
- Databricks streaming job state != RUNNING for > 5 minutes
- OR Kafka consumer lag (Databricks group) growing continuously

### Impact
- Delta tables not updated with new events
- Kafka consumer lag growing (events buffered in Kafka)
- No data loss (Kafka retains; checkpoint preserves state)

### Diagnostic Steps
1. Check Databricks job status:
   - Workspace UI → Jobs → manufacturing-streaming → Recent runs
   - Look for error in latest run attempt

2. Common causes:
   a. Cluster failed to start (capacity)
   b. Kafka connectivity lost (security group, VPC peering)
   c. Checkpoint corruption (rare)
   d. Schema incompatibility (new field type mismatch)

### Recovery Steps
1. If cluster capacity issue:
   - Retry job (Databricks auto-retry should handle)
   - If persistent: increase cluster pool size

2. If Kafka connectivity:
   - Verify MSK security group allows Databricks CIDR
   - Verify VPC peering/PrivateLink status
   - Test: from Databricks notebook, telnet to MSK bootstrap

3. If checkpoint corruption:
   - Move checkpoint to backup: s3://checkpoints/sensor-data/ → s3://checkpoints/sensor-data-backup/
   - Restart job with startingOffsets="latest" (accept gap)
   - OR restart with specific Kafka timestamp offset for replay

4. If schema issue:
   - Check error log for "schema mismatch" or "cannot cast"
   - If new field: verify mergeSchema=true is set
   - If type change: fix at source per ADR-012 rules

### Verification
- Job state = RUNNING
- Consumer lag decreasing
- New rows appearing in Delta table:
  SELECT count(*) FROM manufacturing_poc.factory_alpha.sensor_readings
  WHERE ingestion_timestamp > current_timestamp() - INTERVAL 5 MINUTES

### Escalation
- If unresolved after 30 minutes → Architecture Lead
- If Databricks platform issue → Databricks Support ticket

### Prevention
- Configure job retry policy: max 3 retries, 5-min interval
- Set up proactive checkpoint health check (weekly)
- Monitor Kafka connectivity continuously
```

### Sample Runbook: RUN-009 — Data Reconciliation Mismatch

```
## RUN-009: Data Reconciliation Mismatch

### Trigger
- Periodic reconciliation job detects:
  Kafka produced count ≠ (ClickHouse rows + tolerance) 
  OR Kafka produced count ≠ (Delta table rows + tolerance)
- Tolerance: pipeline lag equivalent (e.g., 5 min × event rate)

### Impact
- Potential data loss or duplication detected
- Requires investigation to determine root cause

### Diagnostic Steps
1. Determine which side has fewer records:
   - Kafka offset range: earliest → latest for topic
   - ClickHouse: SELECT count() FROM factory.sensor_data
   - Databricks: SELECT count(*) FROM ...sensor_readings

2. Check time range of discrepancy:
   - Is it recent (pipeline lag — likely OK)?
   - Is it historical (indicates past data loss)?

3. Narrow time window:
   - SELECT count() ... WHERE timestamp BETWEEN X AND Y
   - Compare across all three systems for same window

4. If ClickHouse < Kafka:
   - Check ClickHouse Kafka consumer group lag
   - Check for kafka_skip_broken_messages (system.kafka_consumers)
   - Check dead_letter_queue table

5. If Databricks < Kafka:
   - Check Databricks streaming metrics (input vs output)
   - Check checkpoint for skipped offsets
   - Check for schema errors in driver logs

### Recovery Steps
1. If gap is recent (< 1 hour):
   - Wait for pipeline catch-up
   - Re-verify after 30 minutes

2. If gap is historical:
   - For ClickHouse: replay from Kafka by resetting consumer offset
   - For Databricks: reset checkpoint to earlier offset
   - Verify no duplicates after replay (ReplacingMergeTree / MERGE dedup)

### Verification
- Re-run reconciliation check
- Counts within tolerance

### Escalation
- If data loss confirmed and not recoverable from Kafka → Architecture Lead
- If Kafka retention expired → accept gap, document in incident log

### Prevention
- Run reconciliation check daily (automated)
- Set Kafka retention > max expected recovery time
- Monitor broken message skip count
```

---

## SLO-006: Reconciliation Strategy

### Automated Data Reconciliation

```sql
-- ClickHouse: Count events per hour
SELECT
    toStartOfHour(timestamp) AS hour,
    count() AS ch_count
FROM factory.sensor_data
WHERE timestamp > now() - INTERVAL 24 HOUR
GROUP BY hour
ORDER BY hour;

-- Compare with Kafka offset deltas per hour (external script)
-- Compare with Delta table counts per hour (Databricks SQL)
```

### Reconciliation Schedule

| Check | Frequency | Tolerance | Action on Mismatch |
|-------|-----------|-----------|-------------------|
| Kafka offset vs ClickHouse count | Every hour | ± 5 min × event rate | Alert if exceeds |
| Kafka offset vs Delta count | Every hour | ± 15 min × event rate | Alert if exceeds |
| ClickHouse vs Delta (cross-check) | Daily | ± hourly count variance | Investigate |
| Payload URI validity | Daily (sample 1%) | 0 broken URIs | Alert on any failure |

---

## Persona Review Notes

- **Persona 6 (Reliability/Ops)**: This document directly addresses all P0 findings. SLOs, ownership, failure modes, monitoring, and runbooks are defined.
- **Persona 5 (Security)**: Monitoring includes security-relevant metrics (unauthorized access attempts should be added to CloudTrail monitoring in production).
- **Persona 2 (Storage)**: FSx monitoring covers capacity and throughput. FlexCache metrics included for Phase B.
- **Confidentiality**: ✅ Pass — All thresholds, names, and configurations are generic.
