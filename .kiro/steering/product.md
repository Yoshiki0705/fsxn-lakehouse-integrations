# Product Overview

## Project: FSxN Lakehouse Integrations

Amazon FSx for NetApp ONTAP × S3 Access Points × Lakehouse プラットフォーム統合パターン集。

### Core Value Proposition

- **FSx ONTAP = Enterprise Storage**: NFS/SMB/iSCSI + S3 Access Points による統一ストレージ
- **S3 Access Points = Connection Layer**: Lakehouse プラットフォームとの標準化された接続
- **ONTAP Differentiators**:
  - 重複排除 (Deduplication): 類似データセットのストレージ効率化
  - 圧縮 (Compression): インラインデータ圧縮
  - Snapshot: ポイントインタイムリカバリ
  - FlexClone: 瞬時のデータセットクローン（開発/テスト用）
  - SnapMirror: クロスリージョン DR
  - FabricPool 階層化: コールドデータの自動 S3 ティアリング

### Target Audience

- エンタープライズデータ基盤チーム
- データエンジニア / プラットフォームエンジニア
- クラウドアーキテクト（ストレージ + 分析基盤）
- NetApp / AWS パートナー

### Positioning

FSx ONTAP を「エンタープライズ Data Lakehouse のストレージレイヤー」として位置づけ、
各プラットフォームからのシームレスなアクセスパターンを具体的に示す。

### Key Differentiator vs Native S3

| Aspect | Native S3 | FSxN + S3 AP |
|--------|-----------|--------------|
| Protocol | S3 only | NFS + SMB + iSCSI + S3 |
| Deduplication | None | Inline/Post-process |
| Snapshot | Versioning (object-level) | Volume-level instant |
| Clone | Full copy | FlexClone (zero-copy) |
| Tiering | Lifecycle rules | FabricPool (automatic) |
| Performance | Variable | Consistent (SSD-backed) |
