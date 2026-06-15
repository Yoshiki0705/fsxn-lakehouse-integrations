# Support Inquiry: ClickHouse Cloud ClickPipes × MSK Connectivity

> **Status**: MSK Provisioned deployed; ClickPipes "Incompatible" issue — awaiting ClickHouse Support response
> **Date**: 2026-06-15 (updated)
> **Case**: ClickHouse Support (active)
> **Priority**: High (PoC blocker)

---

## Issue Summary (Updated 2026-06-15)

### Phase 1: MSK Serverless (Resolved)
ClickHouse Cloud ClickPipes cannot connect to MSK Serverless due to DNS resolution failure. MSK Serverless does not support Multi-VPC connectivity.

### Phase 2: MSK Provisioned Multi-VPC (Current Blocker)
MSK Provisioned (kafka.m5.large) is deployed with Multi-VPC connectivity enabled. However, ClickPipes shows the endpoint as **"Incompatible"** in the Reverse Private Endpoint UI, preventing selection.

## Current Error

Without Reverse Private Endpoint:
```
dial tcp: lookup b-2.scram.manufacturingpocm.ahas42.c3.kafka.ap-northeast-1.amazonaws.com on 172.20.0.10:53: no such host
```

With Reverse Private Endpoint enabled:
```
MSK manufacturing-poc Multi-VPC endpoint | Ready | Incompatible
(checkbox disabled — cannot be selected)
```

## Environment

| Component | Details |
|-----------|---------|
| ClickHouse Cloud | Service ID: 81dbfcdc-1127-48d5-9d11-8833db8cebb1, Region: ap-northeast-1, Version: 25.12 |
| MSK Provisioned | Cluster: manufacturing-poc-msk-prov, kafka.m5.large × 2, Kafka 3.6.0 |
| Multi-VPC Bootstrap (SCRAM) | `b-1.scram.manufacturingpocm.ahas42.c3.kafka.ap-northeast-1.amazonaws.com:14001` |
| SASL/SCRAM Secret | `AmazonMSK_manufacturing-poc/clickhouse-user-v3` (custom KMS key) |
| Authentication | SASL/SCRAM-SHA-512 |
| auto.create.topics | Enabled |

## Resolution Timeline

| Date | Action | Result |
|------|--------|--------|
| 2026-06-07 | MSK Serverless tested | ❌ DNS not resolvable from ClickHouse |
| 2026-06-07 | ClickHouse support case opened | Support engineer shared KB article |
| 2026-06-07 | MSK Provisioned (t3.small) created | ❌ t3.small doesn't support Multi-VPC |
| 2026-06-08 | MSK upgraded to kafka.m5.large | ✅ Multi-VPC enabled |
| 2026-06-15 | SASL/SCRAM credentials associated | ✅ Custom KMS key |
| 2026-06-15 | ClickPipes setup attempted | ❌ "Incompatible" on Reverse Private Endpoint |
| 2026-06-15 | Reply sent to ClickHouse Support | 🔄 Awaiting response |

## Open Questions (Sent to ClickHouse Support 2026-06-15)

1. Why does the MSK Multi-VPC endpoint show as "Incompatible" in ClickPipes?
2. Does ClickPipes require a separate VPC Endpoint Service (NLB-based) instead of MSK's native Multi-VPC connectivity?
3. Is there a way to resolve this without enabling MSK Public Access?

## Workaround Options

| Option | Complexity | Security | Notes |
|--------|-----------|----------|-------|
| MSK Public Access + SASL/SCRAM | Low | Medium (TLS + SCRAM) | Fastest workaround |
| NLB → MSK (VPC Endpoint Service) | High | High (PrivateLink) | May be what ClickPipes expects |
| SSH Tunnel (ClickPipes option) | Medium | High | Requires bastion host |
| Wait for ClickHouse Support | — | — | May resolve "Incompatible" flag |

## KB Article Referenced

https://clickhouse.com/docs/knowledgebase/aws-privatelink-setup-for-msk-clickpipes
