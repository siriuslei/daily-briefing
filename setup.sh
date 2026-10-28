#!/usr/bin/env bash
# 一次性部署：建 GitHub 仓库、录入密钥、夸克云端登录、开启播放页。
# 在终端运行: bash setup.sh   （密钥只在你的终端里输入，不经过任何聊天记录）
set -euo pipefail
cd "$(dirname "$0")"
PROFILE_DIR="../../00_个人档案"
QUARK="$HOME/.claude/skills/quarkclouddrive/scripts/quark-drive.cjs"
REPO_NAME="${REPO_NAME:-daily-briefing}"
step() { printf "\n\033[1;32m== %s\033[0m\n" "$1"; }

step "1/7 GitHub 登录"
export PATH="$HOME/.local/bin:$PATH"
command -v gh >/dev/null || { echo "缺少 gh，请先安装 GitHub CLI"; exit 1; }
gh auth status >/dev/null 2>&1 || gh auth login -w -p https
OWNER=$(gh api user -q .login)

step "2/7 创建仓库 $OWNER/$REPO_NAME 并推送代码"
[ -d .git ] || { git init -q -b main; git add -A; git commit -qm "init daily briefing"; }
gh repo view "$OWNER/$REPO_NAME" >/dev/null 2>&1 || gh repo create "$REPO_NAME" --public --source . --push
R="$OWNER/$REPO_NAME"

step "3/7 录入密钥（输入时不显示）"
echo "Gemini API key（在 https://aistudio.google.com/apikey 免费创建）："
gh secret set GEMINI_API_KEY -R "$R"
echo "Gmail 应用专用密码（Google 账号 → 安全性 → 两步验证 → 应用专用密码，16 位）："
gh secret set GMAIL_APP_PASSWORD -R "$R"
gh secret set PROFILE_MD -R "$R" < "$PROFILE_DIR/我的情况.md"
gh secret set FINANCE_MD -R "$R" < "$PROFILE_DIR/理财策略.md"
gh secret list -R "$R" | grep -q PAGES_TOKEN || openssl rand -hex 12 | tee .pages_token | gh secret set PAGES_TOKEN -R "$R"

step "4/7 夸克网盘云端登录（会打开浏览器授权，与本机 Claude 的登录相互独立）"
QENV=(env -u CLAUDECODE -u CLAUDE_CODE_SESSION_ID -u CLAUDE_CODE_ENTRY_POINT -u AI_AGENT CODEX_CI=1)
"${QENV[@]}" node "$QUARK" login
CFG="$(dirname "$(dirname "$QUARK")")/codex/config.json"
[ -f "$CFG" ] || { echo "没找到 $CFG，夸克登录可能未完成"; exit 1; }
KEY=$(openssl rand -hex 32)
mkdir -p state
openssl enc -aes-256-cbc -pbkdf2 -salt -in "$CFG" -out state/quark.enc -pass pass:"$KEY"
printf %s "$KEY" | gh secret set QUARK_KEY -R "$R"

step "5/7 在夸克网盘建「每日新闻播报」文件夹"
FID=$("${QENV[@]}" node "$QUARK" create-folder --dir-path "每日新闻播报" --parent-fid 0 \
  | grep '"type":"result"' | tail -1 | python3 -c "import json,sys;print(json.load(sys.stdin)['data']['fid'])")
gh variable set QUARK_FOLDER_FID -R "$R" -b "$FID"

step "6/7 开启 GitHub Pages 播放页"
gh api -X POST "repos/$R/pages" -f build_type=workflow >/dev/null 2>&1 || gh api -X PUT "repos/$R/pages" -f build_type=workflow >/dev/null
git add -A; git commit -qm "add quark login state" || true; git push -q -u origin main

step "7/7 试跑一期早报（立即发送）"
gh workflow run briefing.yml -R "$R" -f slot=morning -f send_now=true
echo
echo "完成！几分钟后查看运行情况：https://github.com/$R/actions"
[ -f .pages_token ] && echo "播放页：https://$OWNER.github.io/$REPO_NAME/$(cat .pages_token)/  （收藏到手机主屏）"
