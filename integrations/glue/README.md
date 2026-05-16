# AWS Glue Integration / AWS Glue 統合

🌐 [日本語](#日本語) | [English](#english)

---

<a id="english"></a>

## English

### Overview

Use AWS Glue for ETL pipelines with FSx for NetApp ONTAP as both
source and target storage via S3 Access Points. Implements Medallion Architecture.

### Architecture

```
FSxN (Raw/Bronze)                              FSxN (Silver/Gold)
    │                                               ▲
    └── S3 AP (read) ──→ Glue ETL Job ──→ S3 AP (write) ──┘
                              │
                         Transform:
                         - Data quality
                         - Schema normalization
                         - Aggregation
```

### Important: Network Origin

AWS Glue requires S3 Access Points with **internet network origin**.

Reference: [AWS Tutorial - Build ETL pipelines with Glue](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-transform-data-with-glue.html)

### Status: 🚧 Planned

### Planned Content

- [ ] CloudFormation template (Glue Job + Crawler + S3 AP)
- [ ] Glue ETL scripts (PySpark)
- [ ] Medallion architecture implementation (Bronze → Silver → Gold)
- [ ] Data quality checks
- [ ] EventBridge scheduled triggers
- [ ] Documentation (JA/EN)
- [ ] E2E verification tasks

---

<a id="日本語"></a>

## 日本語

### 概要

AWS Glue を使用して FSx for NetApp ONTAP をソースおよびターゲットストレージとする
ETL パイプラインを構築します。メダリオンアーキテクチャを実装します。

### アーキテクチャ

```
FSxN (Raw/Bronze)                              FSxN (Silver/Gold)
    │                                               ▲
    └── S3 AP (読み取り) ──→ Glue ETL Job ──→ S3 AP (書き込み) ──┘
                                  │
                             変換処理:
                             - データ品質チェック
                             - スキーマ正規化
                             - 集計
```

### 重要: ネットワークオリジン

AWS Glue は **インターネットネットワークオリジン** の S3 Access Point が必要です。

参考: [AWS チュートリアル - Glue で ETL パイプラインを構築](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-transform-data-with-glue.html)

### ステータス: 🚧 計画中
