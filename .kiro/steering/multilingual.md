# Multilingual Documentation Rules

## Language Policy

- **Default language**: 日本語 (Japanese)
- **Required translations**: English (must be kept in sync)
- **Code comments**: English only
- **Variable/function names**: English only
- **Commit messages**: English
- **Issue/PR titles**: English

## Documentation Structure

### Project-level docs (`docs/`)
```
docs/
├── ja/          # Japanese (primary)
│   ├── architecture.md
│   ├── getting-started.md
│   └── ...
├── en/          # English (synchronized)
│   ├── architecture.md
│   ├── getting-started.md
│   └── ...
└── images/      # Shared (language-neutral diagrams)
```

### Integration-level docs (`integrations/<vendor>/docs/`)
```
integrations/<vendor>/docs/
├── ja/
│   └── setup-guide.md
└── en/
    └── setup-guide.md
```

## README.md Convention

Top-level README.md uses a language switcher:

```markdown
🌐 [日本語](docs/ja/architecture.md) | [English](docs/en/architecture.md)
```

Integration README.md files may be:
- Bilingual (both languages in one file with sections), OR
- Link-based (pointing to `docs/ja/` and `docs/en/`)

## Synchronization Rules

1. When updating Japanese docs, English docs MUST be updated in the same PR
2. Diagrams in `images/` use English labels (universal)
3. Code snippets are identical in both languages (only surrounding text differs)
4. Technical terms may remain in English in Japanese docs (e.g., "S3 Access Point", "FlexClone")

## Writing Style

### Japanese
- 「です・ます」調（丁寧語）
- 技術用語は英語のまま使用可（初出時にカッコ書きで日本語補足）
- 例: 「S3 Access Point（アクセスポイント）を作成します」

### English
- Technical writing style (clear, concise)
- Use active voice
- Avoid jargon without explanation
