from __future__ import annotations

import argparse
from pathlib import Path

from src import db
from src.config import load_config
from src.dashboard_builder import build_dashboard_data, write_dashboard_files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Dashboard directory. Default: docs/dashboard")
    args = parser.parse_args()

    cfg = load_config()
    dashboard_dir = Path(args.output) if args.output else cfg.root_dir / "docs" / "dashboard"
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    data = build_dashboard_data(conn)
    write_dashboard_files(data, dashboard_dir)
    print(f"[dashboard] wrote {dashboard_dir / 'data' / 'dashboard.json'}")


if __name__ == "__main__":
    main()

