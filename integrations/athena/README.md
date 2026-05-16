# AWS Athena Integration / AWS Athena 統合

🌐 [日本語](#日本語) | [English](#english)

---

<a id="english"></a>

## English

### Overview

Query data on FSx for NetApp ONTAP directly from Amazon Athena using
Glue Data Catalog and S3 Access Points. Serverless, pay-per-query analytics.

### Architecture

```
Athena (Serverless SQL)
    │
    └── Glue Data Catalog
            │
            └── S3 Access Point (internet origin) ──→ FSxN Volume
```

### Important: Network Origin

Athena requires S3 Access Points with **internet network origin**.
VPC-only access points will NOT work with Athena.

Reference: [AWS Tutorial - Query files with Athena](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-query-data-with-athena.html)

### Status: 🚧 Planned

### Planned Content

- [ ] CloudFormation template (Glue Crawler + S3 AP with internet origin)
- [ ] Athena SQL query examples
- [ ] Glue Crawler configuration
- [ ] Partitioned table setup
- [ ] Documentation (JA/EN)
- [ ] E2E verification tasks

---

<a id="日本語"></a>

## 日本語

### 概要

Amazon Athena から FSx for NetApp ONTAP のデータを直接クエリします。
Glue Data Catalog と S3 Access Points を使用したサーバーレス分析です。

### アーキテクチャ

```
Athena (サーバーレス SQL)
    │
    └── Glue Data Catalog
            │
            └── S3 Access Point (インターネットオリジン) ──→ FSxN Volume
```

### 重要: ネットワークオリジン

Athena は **インターネットネットワークオリジン** の S3 Access Point が必要です。
VPC 限定のアクセスポイントは Athena では動作しません。

参考: [AWS チュートリアル - Athena でファイルをクエリ](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-query-data-with-athena.html)

### ステータス: 🚧 計画中
