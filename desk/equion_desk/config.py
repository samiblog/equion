"""설정과 지난 화면 — 닫았다 열면 이어지게 사용자 폴더의 `config.json` 하나에 적는다(프로젝트 폴더에는 쓰지 않는다).

    %APPDATA%\\EquionDesk\\config.json      (시험·점검은 환경 변수 EQUION_DESK_CONFIG_DIR 로 다른 곳에)

- `tabs`·`active`: 열어 둔 프로젝트 탭과 고른 탭 · `recent`: 최근에 연 폴더 · `window`: 창 크기
- `client`: 화면 설정(테마·글자 크기·사이드바와 터미널의 폭과 보임) — 화면이 고치는 것은 `CLIENT` 에 있는 이름·형식뿐이다
- `views`: 프로젝트마다 화면 상태(연 탭·고른 탭·쓰던 식 초안·펼친 폴더) — 화면이 주는 JSON 을 크기만 재고 그대로 둔다

읽지 못한 파일(손으로 고치다 깨짐)은 건드리지 않고 기본값으로 뜬다 — 다음 저장 때 `config.json.bad` 로 옮겨 둔다.
틀은 Lectern 0.69.1(`cd7fb26`)의 `lectern/config.py` 를 따랐다(desk/THIRD-PARTY-NOTICES.md).
"""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

CONFIG_VERSION = 1
MAX_TABS = 8            # 한 번에 여는 프로젝트 탭
MAX_RECENT = 12
MAX_VIEWS = 30          # 화면 상태를 기억하는 프로젝트 수
MAX_VIEW_BYTES = 64 * 1024

THEMES = ("auto", "light", "dark")
# 화면이 고칠 수 있는 설정: 이름 → (형식, 검사)
CLIENT: dict[str, Any] = {
    "theme": lambda v: v in THEMES,
    "font_scale": lambda v: isinstance(v, int) and not isinstance(v, bool) and 80 <= v <= 140,
    "side_width": lambda v: v is None or (isinstance(v, int) and not isinstance(v, bool) and 180 <= v <= 1600),
    "term_width": lambda v: v is None or (isinstance(v, int) and not isinstance(v, bool) and 240 <= v <= 2400),
    "side_visible": lambda v: isinstance(v, bool),
    "term_visible": lambda v: isinstance(v, bool),
    "term_follow": lambda v: isinstance(v, bool),      # 터미널 색이 창의 바탕(밝게·어둡게)을 따른다 — 끄면 늘 어둡게(D48)
    "right_split": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and 0.15 <= v <= 0.85,   # 오른쪽 열의 터미널 높이 비율(DESK_V2)
    "cmd_top": lambda v: isinstance(v, bool),          # 명령 창을 터미널 위에
    "term_font_size": lambda v: isinstance(v, int) and not isinstance(v, bool) and 10 <= v <= 24,   # 터미널 글자 크기(px) — 화면 글자 크기와 따로
}
CLIENT_DEFAULTS: dict[str, Any] = {"theme": "auto", "font_scale": 100, "side_width": None, "term_width": None,
                                   "side_visible": True, "term_visible": True, "term_follow": True, "right_split": 0.62, "cmd_top": False,
                                   "term_font_size": 14}


def config_dir() -> Path:
    custom = os.environ.get("EQUION_DESK_CONFIG_DIR")
    if custom:
        return Path(custom)
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "EquionDesk"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "equion-desk"


def _folder_key(root: str) -> str:
    return os.path.normcase(os.path.abspath(root))


class Config:
    """설정 파일 하나. 고칠 때마다 바로 저장한다(임시 파일에 쓴 뒤 바꿔치기)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else config_dir() / "config.json"
        self._lock = threading.RLock()
        self.load_error: str | None = None
        self._data = self._read()

    def _read(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("not an object")
            data = raw
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            self.load_error = f"{self.path}: {exc}"
        return self._clean(data)

    @staticmethod
    def _clean(data: dict[str, Any]) -> dict[str, Any]:
        """형식이 맞는 것만 남긴다 — 손으로 고친 파일의 틀린 값은 기본값으로."""
        def folders(value: Any, limit: int) -> list[str]:
            return [v for v in value if isinstance(v, str) and v][:limit] if isinstance(value, list) else []

        client = dict(CLIENT_DEFAULTS)
        if isinstance(data.get("client"), dict):
            client.update({k: v for k, v in data["client"].items() if k in CLIENT and CLIENT[k](v)})
        window = data.get("window")
        ok_window = (isinstance(window, dict) and all(isinstance(window.get(k), int) and not isinstance(window.get(k), bool)
                                                       for k in ("width", "height")))
        views = {k: v for k, v in data["views"].items() if isinstance(k, str) and isinstance(v, dict)} if isinstance(data.get("views"), dict) else {}
        active = data.get("active")
        return {"version": CONFIG_VERSION, "tabs": folders(data.get("tabs"), MAX_TABS),
                "active": active if isinstance(active, int) and not isinstance(active, bool) and active >= 0 else 0,
                "recent": folders(data.get("recent"), MAX_RECENT), "window": dict(window) if ok_window else None,
                "client": client, "views": views}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.load_error:
            # 읽지 못한 파일을 덮어쓰기 전에 옆에 남긴다
            try:
                os.replace(self.path, self.path.with_name(self.path.name + ".bad"))
            except OSError:
                pass
            self.load_error = None
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

    def _write(self) -> None:
        try:
            self._save()
        except OSError:
            pass     # 설정을 저장하지 못해도 앱은 돈다(읽기 전용 폴더 등)

    # ---- 읽기 -----------------------------------------------------------------------------------

    def get(self, key: str) -> Any:
        with self._lock:
            return json.loads(json.dumps(self._data.get(key)))

    def client(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data["client"])

    def view(self, root: str) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._data["views"].get(_folder_key(root)) or {}))

    # ---- 고치기 ---------------------------------------------------------------------------------

    def update_client(self, patch: dict[str, Any]) -> dict[str, Any]:
        """화면 설정을 고친다. 모르는 이름·틀린 형식은 버린다. 고친 뒤의 설정을 돌려준다."""
        with self._lock:
            good = {k: v for k, v in patch.items() if k in CLIENT and CLIENT[k](v)}
            if good:
                self._data["client"].update(good)
                self._write()
            return dict(self._data["client"])

    def set_window(self, width: int, height: int) -> None:
        with self._lock:
            self._data["window"] = {"width": int(width), "height": int(height)}
            self._write()

    def set_tabs(self, roots: list[str], active: int = 0) -> None:
        with self._lock:
            roots = roots[:MAX_TABS]
            if self._data["tabs"] == roots and self._data["active"] == active:
                return
            self._data["tabs"], self._data["active"] = list(roots), max(0, int(active))
            self._write()

    def add_recent(self, root: str) -> None:
        with self._lock:
            key = _folder_key(root)
            rest = [r for r in self._data["recent"] if _folder_key(r) != key]
            self._data["recent"] = ([root] + rest)[:MAX_RECENT]
            self._write()

    def forget_recent(self, root: str) -> None:
        with self._lock:
            key = _folder_key(root)
            self._data["recent"] = [r for r in self._data["recent"] if _folder_key(r) != key]
            self._write()

    def set_view(self, root: str, view: dict[str, Any]) -> bool:
        """프로젝트의 화면 상태를 적는다. 너무 크면 버리고 False."""
        if len(json.dumps(view, ensure_ascii=False).encode("utf-8")) > MAX_VIEW_BYTES:
            return False
        with self._lock:
            views = self._data["views"]
            key = _folder_key(root)
            views.pop(key, None)
            views[key] = view                       # 방금 쓴 것이 맨 뒤 — 오래된 것부터 버린다
            for old in list(views)[:-MAX_VIEWS]:
                del views[old]
            self._write()
            return True
