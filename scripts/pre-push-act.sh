#!/usr/bin/env bash
# push 直前に act で PR ワークフローをローカル実行するスクリプト
# ACT_ARGS でジョブ絞り込み可（例: ACT_ARGS="-j backend-unit"）

set -euo pipefail

ACT_ARGS="${ACT_ARGS:-}"

echo "[pre-push] act pull_request を実行します (${ACT_ARGS})"
act pull_request ${ACT_ARGS}

echo "[pre-push] act 完了: push を続行できます"
