# Data Perimeter Pattern

🌐 [日本語](data-perimeter-pattern-ja.md) | English

## Purpose

Define network and identity boundaries around raw file access and metadata queries for regulated environments.

## Layers

| Layer | Control | Purpose |
|-------|---------|---------|
| S3 Access Point policy | Resource policy on AP | Restrict which IAM principals can access files |
| VPC origin on S3 AP | Network restriction | Ensure requests come from specific VPC |
| VPC endpoint policy | Endpoint-level filter | Restrict which S3/Glue/Bedrock actions are allowed |
| IAM identity policy | Principal permissions | Least-privilege per role |
| IAM permission boundary | Guardrail | Prevent privilege escalation |
| SCP (Organizations) | Account-level guardrail | Prevent disabling controls |
| Lake Formation | Data governance | Table/column/row access on metadata |

## Recommended Configuration

```
For regulated environments, combine:
1. S3 Access Point policies (restrict principals + prefixes)
2. VPC endpoint policies (restrict actions to specific buckets/tables)
3. IAM identity policies (least-privilege per Lambda/role)
4. AWS Organizations SCPs (prevent disabling CloudTrail, LF, etc.)
5. Lake Formation grants (metadata query governance)
```

## References

- [S3 Access Points VPC origin](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-points-vpc.html)
- [VPC endpoint policies](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-access.html)
- [Data perimeter on AWS](https://docs.aws.amazon.com/whitepapers/latest/building-a-data-perimeter-on-aws/building-a-data-perimeter-on-aws.html)
