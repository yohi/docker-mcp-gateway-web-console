import { CatalogItem } from '@/lib/types/catalog';
import { ContainerInfo } from '@/lib/types/containers';

/**
 * バックエンドと同じルールでコンテナ名を正規化する。
 * - 禁則文字をハイフンに置換
 * - 先頭末尾の . / _ / - を除去
 * - 先頭が英数字でない場合は mcp- を付与
 * - 128 文字で切り詰め
 */
export function normalizeContainerName(name: string): string {
  let normalized = name.trim().replace(/[^a-zA-Z0-9_.-]+/g, '-');
  normalized = normalized.replace(/^[-_.]+|[-_.]+$/g, '');
  if (!normalized) normalized = 'mcp-server';
  if (!/^[a-zA-Z0-9]/.test(normalized)) normalized = `mcp-${normalized}`;
  return normalized.slice(0, 128);
}

/**
 * カタログ項目とコンテナが同一と見なせるか判定する。
 * - イメージが一致
 * - 正規化した名前が一致
 * - ラベル mcp.original_name が一致
 */
export function matchCatalogItemContainer(
  item: CatalogItem,
  container: ContainerInfo
): boolean {
  if (container.image === item.docker_image) return true;

  const normalizedItem = normalizeContainerName(item.name);
  const normalizedContainer = normalizeContainerName(container.name);
  if (normalizedItem === normalizedContainer) return true;

  const original = container.labels?.['mcp.original_name'];
  if (original && normalizeContainerName(original) === normalizedItem) return true;

  return false;
}

