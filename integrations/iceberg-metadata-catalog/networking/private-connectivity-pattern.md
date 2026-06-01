# Private Connectivity Pattern

🌐 [日本語](private-connectivity-pattern-ja.md) | English

## Purpose

Document which AWS services in this architecture require VPC endpoints for private connectivity in production.

## Required VPC Endpoints

| Service | Endpoint Type | Required For |
|---------|:---:|---|
| S3 | Gateway | FSx S3 AP access, S3 Tables data, batch I/O |
| Bedrock Runtime | Interface | Real-time AI classification + embeddings |
| Bedrock | Interface | Batch inference job management |
| SQS | Interface | FPolicy event queue |
| Lambda (if in VPC) | — | Outbound via NAT or endpoints |
| Glue | Interface | Glue Iceberg REST endpoint |
| OpenSearch Serverless | Interface | Vector search indexing + queries |
| CloudWatch Logs | Interface | Lambda logging |
| STS | Interface | AssumeRole for cross-service access |

## Network Architecture

```
┌─────────────────────────────────────────────────────────┐
│  VPC (Private Subnets)                                   │
│                                                          │
│  Lambda ──→ S3 Gateway Endpoint ──→ FSx S3 AP           │
│         ──→ Bedrock Interface Endpoint ──→ Bedrock      │
│         ──→ SQS Interface Endpoint ──→ SQS             │
│         ──→ Glue Interface Endpoint ──→ Glue REST      │
│         ──→ OpenSearch Interface Endpoint ──→ AOSS      │
│                                                          │
│  No NAT Gateway required for AWS service access          │
└─────────────────────────────────────────────────────────┘
```

## Production Checklist

- [ ] All Lambda functions in private subnets
- [ ] S3 Gateway endpoint with route table association
- [ ] Interface endpoints for Bedrock, SQS, Glue, OpenSearch, CloudWatch Logs, STS
- [ ] VPC endpoint policies restricting to required actions only
- [ ] Security groups on interface endpoints (restrict source to Lambda SG)
- [ ] VPC Flow Logs enabled for audit
- [ ] No public internet egress for data-plane operations
