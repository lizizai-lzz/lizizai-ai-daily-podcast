#!/usr/bin/env bash
# init_biography_workspace.sh
# 在当前工作区根目录下创建 biography-{slug}/ 标准目录结构。
# 用法：bash init_biography_workspace.sh {人物英文 slug}
# 示例：bash init_biography_workspace.sh sam-altman

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <person-slug>" >&2
  echo "Example: $0 sam-altman" >&2
  exit 1
fi

SLUG="$1"
# 把可能传入的空格/大写规范化
SLUG="$(echo "$SLUG" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')"

TARGET="./biography-${SLUG}"

if [ -d "$TARGET" ]; then
  echo "⚠️  Directory already exists: $TARGET" >&2
  echo "   Pass --force as the second arg to wipe and recreate." >&2
  if [ "${2:-}" = "--force" ]; then
    rm -rf "$TARGET"
    echo "   Removed existing directory." >&2
  else
    exit 1
  fi
fi

mkdir -p "$TARGET/00_raw"
touch "$TARGET/00_raw/anysearch-bio.md"
touch "$TARGET/00_raw/anysearch-coverage.md"
touch "$TARGET/00_raw/anysearch-controversy.md"
touch "$TARGET/00_raw/social-twitter.md"
touch "$TARGET/00_raw/social-others.md"

touch "$TARGET/10_source.md"
touch "$TARGET/20_outline.md"
touch "$TARGET/30_draft.md"
touch "$TARGET/40_final.md"

cat > "$TARGET/README.md" <<EOF
# Biography Workspace: ${SLUG}

Created by biography-writer skill.

## Pipeline

- [ ] 1. 素材收集 → \`00_raw/\`
- [ ] 2. 母文沉淀 → \`10_source.md\`
- [ ] 3. 大纲设计 → \`20_outline.md\`
- [ ] 4. 传记生成 → \`30_draft.md\`
- [ ] 5. 去 AI 味 → \`40_final.md\`
EOF

echo "✅ Workspace created: $TARGET"
echo "   - 00_raw/ (5 empty source files)"
echo "   - 10_source.md (empty)"
echo "   - 20_outline.md (empty)"
echo "   - 30_draft.md (empty)"
echo "   - 40_final.md (empty)"
echo "   - README.md"
