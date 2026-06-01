# Bedrock Private Connectivity

## Purpose

For sensitive workloads, ensure Bedrock API calls and batch inference data never traverse the public internet.

## Configuration

### VPC Interface Endpoints

| Service | Endpoint | Purpose |
|---------|----------|---------|
| Bedrock Runtime | `com.amazonaws.<region>.bedrock-runtime` | Real-time inference (Vision, Embeddings) |
| Bedrock | `com.amazonaws.<region>.bedrock` | Batch inference job management |
| S3 | `com.amazonaws.<region>.s3` (Gateway) | Batch input/output data |

### Security Controls

- Use VPC interface endpoints for Bedrock Runtime
- Use S3 VPC gateway endpoint for batch input/output
- Restrict S3 bucket policies by VPC endpoint ID (`aws:sourceVpce`)
- Enable VPC Flow Logs for network evidence
- Lambda functions in private subnets (no public IP)

### Batch Inference Security

```
Lambda (private subnet)
  → VPC endpoint → Bedrock (create batch job)
  → S3 VPC endpoint → input JSONL / output results
  
No NAT gateway needed for Bedrock or S3 access.
```

## References

- [Bedrock VPC endpoints](https://docs.aws.amazon.com/bedrock/latest/userguide/usingVPC.html)
- [Bedrock batch inference VPC](https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference-vpc.html)
