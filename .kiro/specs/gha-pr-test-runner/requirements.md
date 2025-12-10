# Requirements Document

## Introduction
PR 作成時に既存テストを自動実行し、ubuntu-slim ランナーでの互換性と nektos/act によるローカル再現性を確保することで、レビュー前に品質を担保する。

## Requirements

### Requirement 1: PR イベントでの自動テスト実行
**Objective:** コードレビュアーとして、PR 作成や更新時に必ずテスト結果を確認できるようにしたい。そうすれば不具合を早期に検出し、マージを安全に行える。

#### Acceptance Criteria
1. WHEN PR が open/reopen/synchronize されたとき THEN CI ワークフローは自動で起動し既存テストジョブを開始する。
2. WHEN CI ワークフローが ubuntu-slim ランナー上で実行されるとき THEN 全テストジョブはタイムアウトや依存欠如なく完走する。
3. IF いずれかのテストジョブが失敗したとき THEN ワークフローは失敗ステータスを報告しマージブロック対象として表示する。
4. WHERE ターゲットがデフォルトブランチへの PR であるとき THEN ワークフロー結果は必須チェックとして GitHub 上に可視化される。

### Requirement 2: 既存テストスイートの網羅実行
**Objective:** 開発者として、バックエンドとフロントエンドの既存テストが PR ごとに一貫して実行されてほしい。そうすれば回帰を防ぎ品質を維持できる。

#### Acceptance Criteria
1. WHEN バックエンドテストジョブが実行されるとき THEN 既存の Pytest ベースのスイートが全件実行され結果が収集される。
2. WHEN フロントエンドユニットテストジョブが実行されるとき THEN 既存の Jest/Testing Library スイートが全件実行され結果が収集される。
3. WHERE E2E/Playwright テストが設定されているとき THEN 必要な依存を満たした上で実行するか、実行対象外とする理由をジョブログに明示する。
4. WHEN テストジョブが依存キャッシュを利用できるとき THEN 再実行時にキャッシュを活用し過剰なダウンロードを回避する。

### Requirement 3: nektos/act によるローカル再現性
**Objective:** 開発者として、push 前にローカルで CI ジョブを再現し、クラウド実行前に失敗を検知したい。そうすれば無駄な PR 更新を防げる。

#### Acceptance Criteria
1. WHEN 開発者が `act pull_request` を実行するとき THEN GitHub Actions と同じジョブ構成が ubuntu-slim イメージを用いてローカル実行される。
2. WHERE ワークフローがシークレットや環境変数を要求するとき THEN act 実行向けの設定手順またはプレースホルダー指定方法がリポジトリ内で参照できる。
3. IF ローカル実行でクラウド特有のサービスに依存する部分があるとき THEN 代替手順またはスキップ条件が明示され、act 実行が中断しない。
