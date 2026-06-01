# DR とカタログ再バインド

🌐 日本語 | [English](snapmirror-catalog-rebinding.md)

## 課題

DR フェイルオーバー（SnapMirror）が発生すると、メタデータカタログにはプライマリボリュームの S3 Access Point エイリアスとボリューム ID への参照が含まれています。フェイルオーバー後、これらの参照は古くなります。

## フェイルオーバー後に変わるもの

| 項目 | プライマリ | DR セカンダリ |
|------|---------|-------------|
| Volume ID | オリジナル | 新規（デスティネーションボリューム） |
| S3 Access Point alias | プライマリ AP エイリアス | 新規 AP エイリアス（DR ボリュームに作成が必要） |
| Junction path | 異なる場合あり | マウントポイントを確認 |
| SVM | プライマリ SVM | DR SVM |

## DR 用の推奨カタログカラム

```yaml
columns:
  - source_volume_id        # ファイルが発見されたオリジナルボリューム
  - current_volume_id       # アクティブボリューム（フェイルオーバー後に更新）
  - source_s3ap_alias       # オリジナル S3 AP エイリアス
  - current_s3ap_alias      # アクティブ S3 AP エイリアス（フェイルオーバー後に更新）
  - catalog_environment     # primary / dr / test
```

## フェイルオーバー手順

1. SnapMirror デスティネーションボリュームをアクティベート
2. デスティネーションボリュームに S3 Access Point を作成
3. メタデータテーブルの `current_volume_id` と `current_s3ap_alias` を更新
4. Athena クエリが新しい AP に解決されることを確認
5. Lambda 環境変数（AP エイリアス）を更新
6. AI エンリッチメントパイプラインの接続性を検証

## FSx for ONTAP SnapMirror に関する注意事項

- ボリュームレベル SnapMirror はサポートされている
- SVM-DR は FSx for ONTAP ではサポートされていない
- 同期 SnapMirror はサポートされていない
- 最小レプリケーション間隔: 5 分
- RPO はレプリケーションスケジュールと変更率に依存

## 参考

- [FSx for ONTAP データ保護](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/snapmirror-ontap.html)
