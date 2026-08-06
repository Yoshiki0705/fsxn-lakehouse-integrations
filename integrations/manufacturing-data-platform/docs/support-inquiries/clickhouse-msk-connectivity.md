# Support Inquiry: ClickHouse Cloud ClickPipes × MSK Connectivity

> **Status**: ✅ ClickHouse Support engineer assigned — awaiting PrivateLink guidance
> **Date**: 2026-06-17 (updated)
> **Case**: ClickHouse Support (active, follow-up case created)
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
dial tcp: lookup b-2.scram.msk-cluster.xxxxx.kafka.ap-northeast-1.amazonaws.com on 198.51.100.53:53: no such host
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
| Multi-VPC Bootstrap (SCRAM) | `b-1.scram.msk-cluster.xxxxx.kafka.ap-northeast-1.amazonaws.com:14001` |
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
| **2026-06-17** | **ClickHouse Support follow-up case created** | **✅ Engineer assigned, awaiting PrivateLink guidance** |

## Updated Questions (2026-06-17)

ClickHouse Support has confirmed the follow-up and an engineer will provide guidance. The key questions now are:

1. Should we use ClickPipes **"Reverse Private Endpoint"** for AWS PrivateLink to MSK?
2. If yes:
   - What **VPC Endpoint Service** configuration is needed on the MSK/customer side?
   - What **ClickPipes configuration** is required for MSK Provisioned + SCRAM over PrivateLink?
3. Is MSK's native Multi-VPC connectivity compatible with ClickPipes, or must we use a separate NLB-based VPC Endpoint Service?

## Expected Next Steps (Pending Support Response)

Based on the KB article and "Reverse Private Endpoint" UI, the likely solution path:

```
Option A: ClickPipes Reverse Private Endpoint (most likely)
  1. Customer creates NLB targeting MSK broker ENIs
  2. Customer creates VPC Endpoint Service (NLB-backed)
  3. ClickHouse creates VPC Endpoint in their VPC → connects to our NLB
  4. ClickPipes uses the private endpoint for Kafka consumption
  
Option B: MSK Multi-VPC native (if supported by ClickPipes)
  - ClickHouse Support may provide a way to resolve Multi-VPC DNS
  - Possible: ClickPipes adds MSK Multi-VPC DNS resolution support

Option C: MSK Public Access (workaround, lower security)
  - Enable public access on MSK with SASL/SCRAM + TLS
  - Fastest but least secure
```

**Action when response arrives**: Implement the recommended approach and update this document with configuration details.

## Workaround Options

| Option | Complexity | Security | Notes |
|--------|-----------|----------|-------|
| MSK Public Access + SASL/SCRAM | Low | Medium (TLS + SCRAM) | Fastest workaround |
| NLB → MSK (VPC Endpoint Service) | High | High (PrivateLink) | May be what ClickPipes expects |
| SSH Tunnel (ClickPipes option) | Medium | High | Requires bastion host |
| Wait for ClickHouse Support | — | — | May resolve "Incompatible" flag |

## KB Article Referenced

https://clickhouse.com/docs/knowledgebase/aws-privatelink-setup-for-msk-clickpipes
