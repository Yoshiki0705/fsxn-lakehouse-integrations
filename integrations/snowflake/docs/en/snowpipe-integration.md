🌐 **English** | [日本語](../ja/snowpipe-integration.md)

# Snowpipe + FSx for ONTAP Integration Guide

## Overview

This guide explains how to automatically ingest data into Snowflake tables
when new files are added to FSx for NetApp ONTAP using Snowpipe.

## Challenge: FSx for ONTAP and S3 Event Notifications

FSx for ONTAP's S3 protocol does not natively support S3 Event Notifications.
Therefore, alternative patterns are needed for Snowpipe `AUTO_INGEST`.

## Recommended Patterns

### Pattern A: Lambda Polling (Recommended)

```
┌──────────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐    ┌──────────┐
│EventBridge│──▶│  Lambda  │──▶│  SNS    │──▶│Snowflake │──▶│Snowpipe  │
│(Schedule) │   │(List new │   │  Topic  │   │  SQS     │   │(COPY INTO)│
│ 1min/5min │   │ files)   │   │         │   │          │   │          │
└──────────┘    └──────────┘    └─────────┘    └──────────┘    └──────────┘
```

**Pros:** Simple, configurable interval, low cost
**Cons:** Not real-time (1-5 min delay)

### Pattern B: ONTAP FPolicy (Advanced)

Real-time file operation detection via ONTAP FPolicy external server.

**Pros:** Real-time, file-operation granularity
**Cons:** Requires FPolicy server, complex setup

### Pattern C: Manual Refresh (Development)

```sql
ALTER PIPE FSXN_EVENTS_PIPE REFRESH;
```

## Setup Steps

1. Set `EnableSnowpipe=true` in CloudFormation
2. Create Snowpipe (`06_snowpipe.sql`)
3. Get notification_channel from `SHOW PIPES`
4. Subscribe Snowflake SQS to SNS Topic
5. Deploy Lambda polling function
6. Configure EventBridge schedule rule
