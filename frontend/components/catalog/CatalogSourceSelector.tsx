'use client';

import { CATALOG_SOURCES, CatalogSourceId } from '@/lib/constants/catalogSources';

/**
 * CatalogSourceSelector Props
 *
 * 親コンポーネントから選択状態と変更通知を受け取る制御コンポーネント
 */
export interface CatalogSourceSelectorProps {
    /** 現在選択されているソースID */
    selectedSource: CatalogSourceId;
    /** ソース変更時のコールバック */
    onSourceChange: (source: CatalogSourceId) => void;
    /** 無効化フラグ（ローディング中など） */
    disabled?: boolean;
}

/**
 * CatalogSourceSelector
 *
 * プリセットされたカタログソースをセレクタから選択できるUIを提供。
 * フリーフォームのURL入力は提供しない（Requirements 5.3）。
 *
 * @see design.md CatalogSourceSelector セクション
 * @requirements 1.1, 5.3
 */
export default function CatalogSourceSelector({
    selectedSource,
    onSourceChange,
    disabled = false,
}: CatalogSourceSelectorProps) {
    const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        onSourceChange(e.target.value as CatalogSourceId);
    };

    return (
        <div
            className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4"
            data-testid="catalog-source-selector"
        >
            <label
                htmlFor="catalog-source-select"
                className="text-sm font-medium text-gray-700"
            >
                カタログソース
            </label>
            <select
                id="catalog-source-select"
                value={selectedSource}
                onChange={handleChange}
                disabled={disabled}
                className="flex-1 max-w-xs px-3 py-2 border border-gray-300 rounded-md bg-white
                   focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
                   disabled:bg-gray-100 disabled:cursor-not-allowed
                   text-sm transition-colors"
            >
                {CATALOG_SOURCES.map((source) => (
                    <option key={source.id} value={source.id}>
                        {source.label}
                    </option>
                ))}
            </select>
        </div>
    );
}
