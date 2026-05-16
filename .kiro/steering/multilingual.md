---
inclusion: auto
---

# Bilingual Documentation Rules

## Language Policy

- **Default language**: Japanese (日本語)
- **Required translations**: English (must be kept in sync)
- **Code comments**: English only
- **Variable/function names**: English only
- **Commit messages**: English
- **Issue/PR titles**: English

## Language Switcher

Every user-facing document MUST include a language switcher at the top:

```markdown
🌐 [日本語](path/to/ja/doc.md) | [English](path/to/en/doc.md)
```

For single-file bilingual documents (like README.md, tasks.md):

```markdown
🌐 [日本語](#日本語) | [English](#english)
```

## What Requires Bilingual Support

### MUST be bilingual:
- README.md (all levels)
- docs/ja/ and docs/en/ (all files)
- integrations/<vendor>/docs/ja/ and docs/en/
- integrations/<vendor>/README.md
- tasks.md
- use-cases/<name>/README.md

### English only (no translation needed):
- Code files (.py, .tf, .yaml, .sql, .sh)
- Code comments
- .gitignore, LICENSE, package.json
- .kiro/ steering files (developer-facing)
- Test files

## Synchronization Rules

1. JA and EN docs must have matching section structure
2. Code blocks must be identical in both languages
3. Diagrams use English labels (shared in docs/images/)
4. Technical terms remain in English in Japanese docs
5. When updating one language, the other MUST be updated in the same commit

## Writing Style

### Japanese
- 「です・ます」調（丁寧語）
- Technical terms in English with optional Japanese gloss: 「S3 Access Point（アクセスポイント）」
- First occurrence only needs gloss

### English
- Technical writing style (clear, concise, active voice)
- Avoid jargon without explanation
