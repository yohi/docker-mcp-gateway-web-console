from __future__ import annotations

import os

from hypothesis import settings

import pytest

from app.services.state_store import StateStore

_DEFAULT_MAX_EXAMPLES = int(os.getenv("HYPOTHESIS_MAX_EXAMPLES", "25"))

# CI/コンテナ環境では I/O 初期化で 200ms を超えることがあるため、
# デッドラインを無効化してフレークを防ぐ。
if "HYPOTHESIS_PROFILE" not in os.environ:
    try:
        settings.register_profile(
            "ci",
            settings(
                deadline=None,
                max_examples=_DEFAULT_MAX_EXAMPLES,
            ),
        )
    except ValueError:
        # プロファイルが既に存在する場合は無視して既定プロファイルを読み込む
        pass
    settings.load_profile("ci")


@pytest.fixture(autouse=True)
def clear_auth_sessions() -> None:
    """各テスト間で認証セッションの永続データをクリーンに保つ。"""
    try:
        from app.services import auth as auth_service  # pylint: disable=import-outside-toplevel

        if hasattr(auth_service, "_INITIALIZED_DB_PATHS"):
            auth_service._INITIALIZED_DB_PATHS.clear()
    except Exception:
        pass
    store = StateStore()
    store.init_schema()
    try:
        with store._connect() as conn:  # type: ignore[attr-defined]
            conn.execute("DELETE FROM auth_sessions")
            conn.commit()
    except Exception:
        # DB がまだ初期化されていない場合などはスキップ
        return
    finally:
        try:
            from app.services import auth as auth_service  # pylint: disable=import-outside-toplevel

            if hasattr(auth_service, "_INITIALIZED_DB_PATHS"):
                auth_service._INITIALIZED_DB_PATHS.clear()
        except Exception:
            pass
