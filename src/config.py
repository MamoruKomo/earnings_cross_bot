from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class AppConfig:
    root_dir: Path
    data_dir: Path
    db_path: Path
    manual_calendar_path: Path
    mock_prices_path: Path
    mock_financials_path: Path
    mock_reactions_path: Path
    margin_interest_path: Path
    learning_profile_path: Path
    lessons_path: Path
    rules_path: Path
    rules_suggestion_path: Path
    timezone: str
    rules: dict[str, Any]

    @property
    def rules_version(self) -> str:
        return str(self.rules.get("version", "unknown"))

    @property
    def model_version(self) -> str:
        return str(self.rules.get("model_version", "rules-plus-llm-mvp"))


def load_env_file(path: Path | None = None) -> None:
    env_path = path or ROOT_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml

        loaded = yaml.safe_load(text)
        return loaded or {}
    except ModuleNotFoundError:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return parse_simple_yaml(text)


def parse_simple_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if "#" in line:
            line = line.split("#", 1)[0].rstrip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = parse_scalar(value)
    return root


def parse_scalar(value: str) -> Any:
    value = value.strip().strip('"').strip("'")
    if value == "":
        return None
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.startswith("[") and value.endswith("]"):
        return json.loads(value)
    try:
        if any(char in value for char in (".", "e", "E")):
            return float(value)
        return int(value)
    except ValueError:
        return value


def load_config() -> AppConfig:
    load_env_file()
    data_dir = ROOT_DIR / "data"
    rules_path = ROOT_DIR / "config" / "rules.yaml"
    return AppConfig(
        root_dir=ROOT_DIR,
        data_dir=data_dir,
        db_path=data_dir / "earnings_cross_bot.db",
        manual_calendar_path=data_dir / "earnings_calendar_manual.csv",
        mock_prices_path=data_dir / "mock_prices.csv",
        mock_financials_path=data_dir / "mock_financials.csv",
        mock_reactions_path=data_dir / "mock_earnings_reactions.csv",
        margin_interest_path=data_dir / "margin_interest_manual.csv",
        learning_profile_path=data_dir / "learning_profile.json",
        lessons_path=data_dir / "lessons.jsonl",
        rules_path=rules_path,
        rules_suggestion_path=ROOT_DIR / "config" / "rules_suggestion.yaml",
        timezone=os.environ.get("TIMEZONE", "Asia/Tokyo"),
        rules=load_yaml(rules_path),
    )
