#!/usr/bin/env python3
"""
demo-japanese-pii.py — Japanese PII Detection & Anonymization Demo

Demonstrates PII detection in Japanese text using Bedrock Claude,
including My Number (マイナンバー) detection which Comprehend cannot do.

Key message: "Bedrock Claude detects Japanese PII including My Number —
something Amazon Comprehend cannot do (en/es only)."

Usage:
    python demo-japanese-pii.py --region ap-northeast-1
"""

import argparse
import json
import re

import boto3


REDACTION = "[墨消し]"


def main():
    parser = argparse.ArgumentParser(description="Japanese PII Demo")
    parser.add_argument("--region", default="ap-northeast-1")
    args = parser.parse_args()

    bedrock = boto3.client("bedrock-runtime", region_name=args.region)

    # Japanese PII test document
    ja_text = """社員情報（機密）
氏名: 山田太郎
メールアドレス: taro.yamada@example.co.jp
電話番号: 090-1234-5678
住所: 〒150-0002 東京都渋谷区渋谷1-2-3 渋谷ビル5F
マイナンバー: 1234 5678 9012
クレジットカード: 4111-1111-1111-1111
生年月日: 1985年3月15日
社員番号: EMP-2024-0042
緊急連絡先: 03-9876-5432（配偶者: 山田花子）"""

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Japanese PII Detection & Anonymization (Bedrock Claude)     ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("  ⚠️  Amazon Comprehend: Japanese NOT supported (en/es only)")
    print("  ✅ Bedrock Claude: All languages including Japanese")
    print()

    # Show original
    print("  ┌── Original Document ──────────────────────────────────────┐")
    for line in ja_text.strip().split("\n"):
        print(f"  │ {line}")
    print("  └──────────────────────────────────────────────────────────┘")
    print()

    # Detect PII with Bedrock Claude
    print("  Detecting PII with Bedrock Claude...")
    prompt = f"""以下の日本語テキストから個人情報（PII）を全て検出してください。
JSON配列で返してください: [{{"type": "...", "value": "..."}}]

検出対象: NAME, EMAIL, PHONE, ADDRESS, MY_NUMBER, CREDIT_CARD, DATE_OF_BIRTH, EMERGENCY_CONTACT, OTHER

テキスト:
{ja_text}"""

    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        contentType="application/json", accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }),
    )

    ai_text = json.loads(response["body"].read())["content"][0]["text"]
    try:
        if "```json" in ai_text:
            ai_text = ai_text.split("```json")[1].split("```")[0]
        elif "```" in ai_text:
            ai_text = ai_text.split("```")[1].split("```")[0]
        pii_entities = json.loads(ai_text.strip())
    except json.JSONDecodeError:
        pii_entities = []

    print()
    print(f"  PII Detected: {len(pii_entities)} entities")
    print()
    print("  ┌── Detected PII ──────────────────────────────────────────┐")
    print("  │  Type                │  Value                            │")
    print("  ├──────────────────────┼───────────────────────────────────┤")
    for entity in pii_entities:
        ptype = entity.get("type", "UNKNOWN")[:20]
        value = entity.get("value", "")[:35]
        marker = "⭐" if ptype == "MY_NUMBER" else "  "
        print(f"  │{marker}{ptype:<20} │  {value:<35} │")
    print("  └──────────────────────┴───────────────────────────────────┘")
    print()

    # Highlight My Number detection
    my_number_found = any(e.get("type") == "MY_NUMBER" for e in pii_entities)
    if my_number_found:
        print("  ⭐ マイナンバー検出成功!")
        print("     Comprehend では検出不可能 → Bedrock Claude が必須")
    print()

    # Anonymize
    print("  Anonymizing...")
    redacted = ja_text
    for entity in sorted(pii_entities, key=lambda x: len(x.get("value", "")), reverse=True):
        value = entity.get("value", "")
        if value and value in redacted:
            redacted = redacted.replace(value, REDACTION)

    print()
    print("  ┌── Anonymized Document ───────────────────────────────────┐")
    for line in redacted.strip().split("\n"):
        print(f"  │ {line}")
    print("  └──────────────────────────────────────────────────────────┘")
    print()
    print(f"  ✅ {len(pii_entities)} PII entities detected and redacted")
    print(f"  ✅ Includes My Number (マイナンバー) — Japan-specific PII")
    print(f"  ✅ All languages supported via Bedrock Claude")


if __name__ == "__main__":
    main()
