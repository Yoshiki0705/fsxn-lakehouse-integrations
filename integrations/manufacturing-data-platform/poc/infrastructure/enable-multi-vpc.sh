#!/bin/bash
set -euo pipefail

# Enable Multi-VPC connectivity on MSK Provisioned cluster
# Run this AFTER broker type upgrade to kafka.m5.large is complete (State = ACTIVE)
#
# Prerequisites:
#   - MSK cluster State = ACTIVE
#   - Broker type = kafka.m5.large (or larger)
#   - Cluster policy already set (allows ClickHouse's published ClickPipes AWS account; see ClickHouse ClickPipes docs for the current account ID)

REGION="ap-northeast-1"
CLUSTER_ARN="arn:aws:kafka:ap-northeast-1:<ACCOUNT_ID>:cluster/manufacturing-poc-msk-prov/f3a0fc3c-e4df-4a62-86ea-c8478657d898-3"

echo "[$(date)] Checking cluster state..."
STATE=$(aws kafka describe-cluster --cluster-arn "$CLUSTER_ARN" --region "$REGION" \
  --query 'ClusterInfo.State' --output text)

if [ "$STATE" != "ACTIVE" ]; then
  echo "ERROR: Cluster is not ACTIVE (current state: $STATE). Wait and retry."
  exit 1
fi

BROKER_TYPE=$(aws kafka describe-cluster --cluster-arn "$CLUSTER_ARN" --region "$REGION" \
  --query 'ClusterInfo.BrokerNodeGroupInfo.InstanceType' --output text)
echo "[$(date)] Cluster ACTIVE. Broker type: $BROKER_TYPE"

if [ "$BROKER_TYPE" = "kafka.t3.small" ]; then
  echo "ERROR: Broker type is still t3.small. Multi-VPC requires m5.large or larger."
  exit 1
fi

echo "[$(date)] Enabling Multi-VPC connectivity..."
CURRENT_VERSION=$(aws kafka describe-cluster --cluster-arn "$CLUSTER_ARN" --region "$REGION" \
  --query 'ClusterInfo.CurrentVersion' --output text)

aws kafka update-connectivity --cluster-arn "$CLUSTER_ARN" --region "$REGION" \
  --current-version "$CURRENT_VERSION" \
  --connectivity-info '{
    "VpcConnectivity": {
      "ClientAuthentication": {
        "Sasl": {
          "Iam": {"Enabled": true},
          "Scram": {"Enabled": true}
        }
      }
    }
  }'

echo "[$(date)] Multi-VPC connectivity update initiated."
echo "         This takes 10-15 minutes. Monitor with:"
echo "         aws kafka describe-cluster --cluster-arn $CLUSTER_ARN --region $REGION --query 'ClusterInfo.State'"
echo ""
echo "After ACTIVE, get the Multi-VPC bootstrap brokers:"
echo "  aws kafka get-bootstrap-brokers --cluster-arn $CLUSTER_ARN --region $REGION"
echo ""
echo "Then configure ClickPipes with the Multi-VPC bootstrap servers."
