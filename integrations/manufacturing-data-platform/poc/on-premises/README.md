# Phase B: On-Premises Deployment Guide

🌐 **English** | [日本語](README-ja.md)

---

> This guide covers the on-premises deployment for Phase B (hybrid architecture).
> Phase A (AWS-only) must be validated first. See `../infrastructure/deploy.sh`.
>
> Architecture Reference: ADR-007 (Phased deployment with FlexCache)

---

## Prerequisites

| Item | Requirement | Notes |
|------|------------|-------|
| On-prem servers | 3+ nodes for Kafka, 2+ for ClickHouse | Instaclustr sizing TBD |
| On-prem NetApp ONTAP | FAS/AFF with ONTAP 9.12+ | S3, FlexCache, intercluster peering |
| Network to AWS | VPN (100+ Mbps) or Direct Connect | For FlexCache + Kafka replication |
| Raspberry Pi(s) | 4B+ or 5, 4GB+ RAM, SSD recommended | Edge gateway devices |
| Instaclustr account | Provisioning API access | Managed Kafka + ClickHouse |

---

## Deployment Order

```
Step 1: Network connectivity (VPN/DX)
Step 2: On-prem ONTAP volume configuration
Step 3: Instaclustr Kafka cluster provisioning
Step 4: Instaclustr ClickHouse provisioning
Step 5: Kafka replication (MirrorMaker 2: on-prem → AWS)
Step 6: FlexCache configuration (FSx for ONTAP ← on-prem ONTAP)
Step 7: Edge device deployment (Raspberry Pi)
Step 8: End-to-end validation
```

---

## Step 1: Network Connectivity

### VPN Setup (Minimum Viable)

```bash
# AWS side: Create VPN Gateway + Customer Gateway + VPN Connection
# Use CloudFormation or manual setup via Console

# Key parameters:
#   Customer Gateway IP: <your on-prem VPN device public IP>
#   VPN type: IPsec
#   Routing: Static or BGP
#   Target VPC: manufacturing-poc-vpc (from Phase A)

# Verify connectivity:
# From an EC2 instance in the VPC:
ping <on-prem-ontap-mgmt-ip>
ssh admin@<on-prem-ontap-mgmt-ip>
```

### Bandwidth Requirements

| Traffic | Bandwidth | Direction | Priority |
|---------|-----------|-----------|----------|
| Kafka replication | 10-50 Mbps | On-prem → AWS | High |
| FlexCache fill | 50-100 Mbps (burst) | On-prem → AWS | Medium |
| Management/monitoring | < 5 Mbps | Bidirectional | Low |
| **Total minimum** | **100 Mbps** | | |

---

## Step 2: On-Prem ONTAP Volume Configuration

### ONTAP CLI Commands

```bash
# Connect to on-prem ONTAP cluster management LIF
ssh admin@<ONPREM_CLUSTER_MGMT_LIF>

# --- Create SVM for factory data ---
vserver create -vserver svm-factory-prod -subtype default \
  -rootvolume svm_factory_root -rootvolume-security-style unix

# --- Enable protocols ---
vserver nfs create -vserver svm-factory-prod -v3 enabled -v4.0 enabled -v4.1 enabled
vserver object-store-server create -vserver svm-factory-prod \
  -object-store-server svm-factory-prod-s3 -is-http-enabled false -is-https-enabled true

# --- Create volumes (matching Phase A design from ADR-013) ---
volume create -vserver svm-factory-prod -volume vol_images \
  -aggregate <aggr_name> -size 300GB -junction-path /vol_images \
  -security-style unix -space-guarantee none \
  -snapshot-policy default -tiering-policy auto -tiering-minimum-cooling-days 31

volume create -vserver svm-factory-prod -volume vol_videos \
  -aggregate <aggr_name> -size 400GB -junction-path /vol_videos \
  -security-style unix -space-guarantee none \
  -snapshot-policy default -tiering-policy auto -tiering-minimum-cooling-days 7

volume create -vserver svm-factory-prod -volume vol_documents \
  -aggregate <aggr_name> -size 100GB -junction-path /vol_documents \
  -security-style mixed -space-guarantee none \
  -snapshot-policy default -tiering-policy auto -tiering-minimum-cooling-days 90

volume create -vserver svm-factory-prod -volume vol_clickhouse_cold \
  -aggregate <aggr_name> -size 200GB -junction-path /vol_clickhouse_cold \
  -security-style unix -space-guarantee none \
  -snapshot-policy default -tiering-policy none

# --- Configure NFS export policy ---
vserver export-policy rule create -vserver svm-factory-prod \
  -policyname default -ruleindex 1 \
  -protocol nfs -clientmatch 192.168.0.0/16 \
  -rorule sys -rwrule sys -superuser sys

# --- Configure ONTAP S3 user and bucket ---
vserver object-store-server user create -vserver svm-factory-prod \
  -user clickhouse-cold-user -comment "ClickHouse cold tier access"
# Note: Access key and secret key are returned — store securely

vserver object-store-server bucket create -vserver svm-factory-prod \
  -bucket factory-clickhouse-cold -size 200GB

vserver object-store-server bucket create -vserver svm-factory-prod \
  -bucket factory-images -size 300GB

# --- Configure intercluster LIF (for FlexCache peering to AWS) ---
network interface create -vserver <cluster-vserver> \
  -lif ic_lif1 -role intercluster \
  -home-node <node1> -home-port <port> -address <IP> -netmask <mask>

# --- Enable audit logging ---
vserver audit create -vserver svm-factory-prod \
  -destination /vol_audit/audit_logs \
  -events file-ops -format evtx \
  -rotate-size 100MB -rotate-limit 50
vserver audit enable -vserver svm-factory-prod
```

---

## Step 3: Instaclustr Kafka Provisioning

### Via Instaclustr Terraform Provider (Recommended)

```hcl
# terraform/instaclustr-kafka.tf

resource "instaclustr_kafka_cluster" "factory_kafka" {
  cluster_name = "manufacturing-poc-kafka"
  
  node_size    = "KFK-PRD-m5.large-250"  # Adjust per Instaclustr sizing
  kafka_version = "3.6.0"
  
  # On-premises deployment
  private_network_cluster = true
  
  # Authentication
  allow_delete_topics = true
  auto_create_topics  = false
  
  # SASL/SCRAM enabled
  client_encryption = true
  
  # Node count
  number_of_nodes = 3
  
  # Tags
  tags = {
    project     = "manufacturing-data-platform-poc"
    environment = "poc"
    phase       = "B"
  }
}
```

### Topic Creation (via kafka-topics CLI after cluster is up)

```bash
# Using the topics from config/environment.yaml
BOOTSTRAP="<INSTACLUSTR_BOOTSTRAP_SERVERS>"
SECURITY="--command-config /etc/kafka/client.properties"

kafka-topics.sh --bootstrap-server $BOOTSTRAP $SECURITY \
  --create --topic factory.sensor-data \
  --partitions 12 --replication-factor 3 \
  --config retention.ms=604800000

kafka-topics.sh --bootstrap-server $BOOTSTRAP $SECURITY \
  --create --topic factory.quality-events \
  --partitions 6 --replication-factor 3 \
  --config retention.ms=2592000000

kafka-topics.sh --bootstrap-server $BOOTSTRAP $SECURITY \
  --create --topic factory.system-alerts \
  --partitions 3 --replication-factor 3 \
  --config retention.ms=7776000000
```

---

## Step 4: Instaclustr ClickHouse Provisioning

### Setup

1. Provision ClickHouse cluster via Instaclustr console/API/Terraform
2. Ensure network connectivity to on-prem Kafka (same network)
3. Run `../clickhouse/01_setup_tables.sql` with local Kafka bootstrap servers

### Key Difference from Phase A

```sql
-- Phase B: ClickHouse connects to LOCAL Instaclustr Kafka (not MSK)
-- Replace ${KAFKA_BOOTSTRAP_SERVERS} with Instaclustr on-prem endpoints
-- Replace credentials with Instaclustr SCRAM credentials
-- No WAN latency for Kafka → ClickHouse path (same network)
```

---

## Step 5: Kafka Replication (MirrorMaker 2)

### Purpose

Replicate on-prem Kafka topics to AWS MSK so Databricks can consume without direct on-prem access.

### MirrorMaker 2 Configuration

```properties
# mm2.properties — deploy on a machine with access to both networks

# Clusters
clusters = onprem, aws
onprem.bootstrap.servers = <INSTACLUSTR_BOOTSTRAP_SERVERS>
aws.bootstrap.servers = <MSK_BOOTSTRAP_SERVERS>

# On-prem authentication (SCRAM)
onprem.security.protocol = SASL_SSL
onprem.sasl.mechanism = SCRAM-SHA-512
onprem.sasl.jaas.config = org.apache.kafka.common.security.scram.ScramLoginModule required \
  username="<ONPREM_USERNAME>" password="<ONPREM_PASSWORD>";

# AWS authentication (IAM)
aws.security.protocol = SASL_SSL
aws.sasl.mechanism = AWS_MSK_IAM
aws.sasl.jaas.config = software.amazon.msk.auth.iam.IAMLoginModule required;
aws.sasl.client.callback.handler.class = software.amazon.msk.auth.iam.IAMClientCallbackHandler

# Replication config
onprem->aws.enabled = true
onprem->aws.topics = factory\..*
aws->onprem.enabled = false

# Consumer config
replication.factor = 3
offset-syncs.topic.replication.factor = 3
heartbeats.topic.replication.factor = 3
checkpoints.topic.replication.factor = 3

# Performance
tasks.max = 4
producer.buffer.memory = 67108864
consumer.max.poll.records = 1000
```

### Deployment

```bash
# Run MirrorMaker 2 on an EC2 instance in the VPC (has access to both via VPN)
connect-mirror-maker.sh mm2.properties
```

### Monitoring

```bash
# Check replication lag
kafka-consumer-groups.sh --bootstrap-server <MSK_BOOTSTRAP_SERVERS> \
  --describe --group mm2-onprem-connector
```

---

## Step 6: FlexCache Configuration

### Prerequisites

- VPN/DX connectivity verified (ping from FSx for ONTAP → on-prem ONTAP)
- Intercluster LIFs configured on both sides
- Cluster peering established

### Cluster Peering (run on both clusters)

```bash
# On-prem ONTAP:
cluster peer create -generate-passphrase \
  -peer-addrs <FSX_INTERCLUSTER_LIF_IPs> -encryption true

# FSx for ONTAP (via AWS CLI → ONTAP REST API):
# Use fsxadmin credentials to access ONTAP CLI/REST
cluster peer create -generate-passphrase \
  -peer-addrs <ONPREM_INTERCLUSTER_LIF_IPs> -encryption true

# Accept peering on both sides
cluster peer modify -cluster <peer-cluster> -passphrase <passphrase>
```

### SVM Peering

```bash
# On FSx for ONTAP:
vserver peer create -vserver svm-factory-poc \
  -peer-vserver svm-factory-prod \
  -peer-cluster <onprem-cluster-name> \
  -applications flexcache

# On on-prem ONTAP: accept
vserver peer accept -vserver svm-factory-prod \
  -peer-vserver svm-factory-poc
```

### FlexCache Volume Creation (on FSx for ONTAP — AWS side)

```bash
# Create FlexCache volume on FSx for ONTAP that caches on-prem origin
volume flexcache create -vserver svm-factory-poc \
  -volume vol_images_cache \
  -origin-vserver svm-factory-prod \
  -origin-volume vol_images \
  -size 100GB \
  -junction-path /vol_images_cache \
  -aggr-list <fsxn-aggr>

# Enable write-back mode (GA May 2025)
volume flexcache config modify -vserver svm-factory-poc \
  -volume vol_images_cache -is-writeback-enabled true
```

### Validation

```bash
# From an EC2 instance in the VPC, mount the FlexCache:
mount -t nfs <FSX_NFS_LIF>:/vol_images_cache /mnt/flexcache

# Read a file (first access = cache miss → WAN fetch → cached)
ls /mnt/flexcache/factory-alpha/line-A1/
time cat /mnt/flexcache/factory-alpha/line-A1/2026/06/07/quality_sample.jpg > /dev/null
# First read: ~500ms-3s (WAN)
# Second read: ~10-50ms (cache hit)
```

---

## Step 7: Edge Device Deployment

See `../edge-device/README.md` for Raspberry Pi setup instructions.

---

## Step 8: End-to-End Validation

### Full Hybrid Flow Test

```bash
# 1. Generate event on edge device (Raspberry Pi)
#    → publishes to on-prem Instaclustr Kafka

# 2. Verify event in on-prem ClickHouse (< 5s)
clickhouse-client --query "SELECT count() FROM factory.sensor_data WHERE timestamp > now() - INTERVAL 1 MINUTE"

# 3. Verify event replicated to AWS MSK (check lag)
kafka-consumer-groups.sh --bootstrap-server <MSK_BOOTSTRAP> --describe --group mm2-onprem-connector

# 4. Verify event in Databricks Delta table (< 5 min)
# Run in Databricks notebook:
# SELECT count(*) FROM manufacturing_poc.factory_alpha.sensor_readings
#   WHERE ingestion_timestamp > current_timestamp() - INTERVAL 10 MINUTES

# 5. Verify payload accessible via FlexCache
ls /mnt/flexcache/factory-alpha/line-A1/  # Should show uploaded files

# 6. Verify no data duplication
# On-prem ONTAP: vol_images has the data (ORIGIN)
# FSx FlexCache: vol_images_cache is cache only (not a copy)
df -h /mnt/flexcache  # Cache size << origin size
```

---

## Phase A ↔ Phase B Difference Matrix

| Component | Phase A (AWS) | Phase B (Hybrid) | Change Required |
|-----------|--------------|------------------|----------------|
| Kafka bootstrap | MSK endpoint | Instaclustr on-prem endpoint | Config change only |
| Kafka auth | IAM | SCRAM-SHA-512 | Config change only |
| ClickHouse Kafka Engine | Points to MSK | Points to local Kafka | DDL update (kafka_broker_list) |
| ONTAP volume names | Same | Same | None |
| ONTAP junction paths | Same | Same | None |
| NFS export policy | VPC CIDR (10.0.x.x) | Factory LAN CIDR (192.168.x.x) | Config change |
| Databricks source | MSK directly | MSK (mirror from on-prem) | None (MSK stays) |
| Edge producer target | MSK (direct) | On-prem Kafka (direct) | Config change |
| Payload upload target | FSx for ONTAP (NFS) | On-prem ONTAP (NFS) | Mount point change |
| Payload read (AI/ML) | FSx for ONTAP (NFS) | FlexCache on FSx (NFS) | Mount point change |
| Data copies in AWS | Full (payloads on FSx) | Cache only (FlexCache) | Architecture change |

### What Does NOT Change Between Phases

- Kafka topic names and schemas
- ClickHouse table DDL (only broker_list changes)
- Databricks tables, schemas, catalogs, permissions
- Delta table schemas
- Streaming pipeline code (only bootstrap server config)
- Event message format (JSON schema)
- Deduplication strategy (event_id based)
- Monitoring metrics and thresholds (SLO targets same)
