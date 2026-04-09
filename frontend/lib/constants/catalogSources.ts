/**
 * Catalog Source Presets
 *
 * プリセットされたカタログソースを定義する。
 * ユーザーはこれらのプリセットのみを選択可能（フリーフォームURL入力は不可）。
 *
 * @see design.md Data Contracts & Integration セクション
 */

export const CATALOG_SOURCES = [
    { id: 'local', label: 'Local (dotfiles-ai)' },
    { id: 'docker', label: 'Docker MCP Catalog' },
    { id: 'official', label: 'Official MCP Registry' },
] as const;

export type CatalogSourceId = typeof CATALOG_SOURCES[number]['id'];

/**
 * デフォルトのカタログソースID
 * Requirements 1.3: 初回表示時は Docker をデフォルトに設定
 * 統合対応: dotfiles-ai のローカル設定をデフォルトにする
 */
export const DEFAULT_CATALOG_SOURCE: CatalogSourceId = 'local';

/**
 * ソースIDからラベルを取得するヘルパー
 */
export function getSourceLabel(sourceId: CatalogSourceId): string {
    const source = CATALOG_SOURCES.find((s) => s.id === sourceId);
    return source?.label ?? sourceId;
}
