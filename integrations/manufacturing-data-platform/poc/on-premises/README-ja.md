# Phase B: オンプレミスデプロイガイド

🌐 [English](README.md) | **日本語**

---

> 本ガイドは Phase B（ハイブリッドアーキテクチャ）のオンプレミスデプロイを対象。
> Phase A（AWS のみ）を先に検証すること。`../infrastructure/deploy.sh` 参照。
>
> アーキテクチャ参照: ADR-007（FlexCache によるフェーズ別デプロイ）

---

## 前提条件

| 項目 | 要件 | 備考 |
|------|------|------|
| オンプレサーバー | Kafka 用 3+ ノード、ClickHouse 用 2+ ノード | Instaclustr サイジング TBD |
| オンプレ NetApp ONTAP | FAS/AFF、ONTAP 9.12+ | S3, FlexCache, インタークラスターピアリング |
| AWS への接続 | VPN (100+ Mbps) または Direct Connect | FlexCache + Kafka レプリケーション用 |
| Raspberry Pi | 4B+ or 5、4GB+ RAM、SSD 推奨 | エッジゲートウェイデバイス |
| Instaclustr アカウント | プロビジョニング API アクセス | マネージド Kafka + ClickHouse |

---

## デプロイ順序

```
Step 1: ネットワーク接続（VPN/DX）
Step 2: オンプレ ONTAP ボリューム設定
Step 3: Instaclustr Kafka クラスタープロビジョニング
Step 4: Instaclustr ClickHouse プロビジョニング
Step 5: Kafka レプリケーション（MirrorMaker 2: オンプレ → AWS）
Step 6: FlexCache 設定（FSx for ONTAP ← オンプレ ONTAP）
Step 7: エッジデバイスデプロイ（Raspberry Pi）
Step 8: エンドツーエンド検証
```

---

## Phase A ↔ Phase B 差分マトリクス

| コンポーネント | Phase A (AWS) | Phase B (ハイブリッド) | 変更内容 |
|-------------|-------------|---------------------|---------|
| Kafka ブートストラップ | MSK エンドポイント | Instaclustr オンプレエンドポイント | 設定変更のみ |
| Kafka 認証 | IAM | SCRAM-SHA-512 | 設定変更のみ |
| ClickHouse Kafka Engine | MSK を参照 | ローカル Kafka を参照 | DDL 更新 (kafka_broker_list) |
| ONTAP ボリューム名 | 同じ | 同じ | 変更なし |
| NFS エクスポートポリシー | VPC CIDR (10.0.x.x) | 工場 LAN CIDR (192.168.x.x) | 設定変更 |
| Databricks ソース | MSK 直接 | MSK（オンプレからのミラー） | 変更なし（MSK 維持） |
| エッジプロデューサー | MSK 直接 | オンプレ Kafka 直接 | 設定変更 |
| ペイロードアップロード先 | FSx for ONTAP (NFS) | オンプレ ONTAP (NFS) | マウントポイント変更 |
| ペイロード読み取り (AI/ML) | FSx for ONTAP (NFS) | FlexCache on FSx (NFS) | マウントポイント変更 |
| AWS でのデータコピー | 全量（ペイロードが FSx 上） | キャッシュのみ（FlexCache） | アーキテクチャ変更 |

### フェーズ間で変更されないもの

- Kafka トピック名とスキーマ
- ClickHouse テーブル DDL（broker_list のみ変更）
- Databricks テーブル、スキーマ、カタログ、権限
- Delta テーブルスキーマ
- ストリーミングパイプラインコード（ブートストラップサーバー設定のみ）
- イベントメッセージフォーマット（JSON スキーマ）
- 重複排除戦略（event_id ベース）
- モニタリングメトリクスと閾値（SLO ターゲット同一）

---

## 詳細手順

各ステップの詳細は英語版 README.md を参照。主要な ONTAP CLI コマンド、Instaclustr Terraform 設定、MirrorMaker 2 設定、FlexCache 作成手順を含む。

## 機密性ノート

本ドキュメントの全デバイス ID、工場名、設定値は**合成プレースホルダー**。デプロイ時に実際の値に置換すること。実認証情報をバージョン管理にコミットしないこと。
