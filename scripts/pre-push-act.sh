#!/usr/bin/env bash
# push 前に act で GHA ジョブを再現し、失敗時は push を止める簡易フック
# 必要に応じて ACT_ARGS でジョブ絞り込み（例: ACT_ARGS="-j backend-unit"）

set -euo pipefail

ACT_ARGS="${ACT_ARGS:-}"

echo "[pre-push] act pull_request を実行します (${ACT_ARGS})"
act pull_request ${ACT_ARGS}

echo "[pre-push] act 完了: push を続行します"
