"""シンプルなメトリクスレコーダーの実装。"""

from collections import defaultdict
from typing import Dict, FrozenSet, List, Optional, Tuple

LabelKey = FrozenSet[Tuple[str, str]]


class MetricsRecorder:
    """カウンタと観測値を保持する軽量レコーダー。"""

    def __init__(self) -> None:
        self._counters: Dict[Tuple[str, LabelKey], int] = defaultdict(int)
        self._observations: Dict[Tuple[str, LabelKey], List[float]] = defaultdict(list)

    def _normalize_labels(self, labels: Optional[Dict[str, str]]) -> LabelKey:
        """ラベルをソート済みの不変キーへ変換する。"""
        if not labels:
            return frozenset()
        return frozenset(sorted(labels.items()))

    def increment(
        self, name: str, labels: Optional[Dict[str, str]] = None, value: int = 1
    ) -> None:
        """カウンタをインクリメントする。"""
        key = (name, self._normalize_labels(labels))
        self._counters[key] += value

    def observe(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """観測値を記録する。"""
        key = (name, self._normalize_labels(labels))
        self._observations[key].append(value)

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> int:
        """指定ラベルのカウンタ値を返す（存在しなければ 0）。"""
        key = (name, self._normalize_labels(labels))
        return self._counters.get(key, 0)

    def get_observations(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ) -> List[float]:
        """指定ラベルの観測値一覧を返す。"""
        key = (name, self._normalize_labels(labels))
        return list(self._observations.get(key, []))
