#!/usr/bin/env bash
# 手動で act を実行して PR ワークフローをローカル再現するスクリプト
# ACT_ARGS でジョブを絞り込み可（例: ACT_ARGS="-j backend-unit"）

set -euo pipefail

ACT_ARGS="${ACT_ARGS:-}"

echo "[act] pull_request を実行します (${ACT_ARGS})"
act pull_request ${ACT_ARGS}

echo "[act] 完了しました"
