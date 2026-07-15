from __future__ import annotations

import argparse
from pathlib import Path

from src import db
from src.config import load_config
from src.dashboard_builder import build_dashboard_data, write_dashboard_files
from src.market_intelligence import load_market_intelligence
from src.daytrade.storage import connect as connect_daytrade, recent_dashboard


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Manager snapshot path. Default: data/manager_snapshot.json")
    args = parser.parse_args()

    cfg = load_config()
    output_path = Path(args.output) if args.output else cfg.data_dir / "manager_snapshot.json"
    conn = db.connect(cfg.db_path)
    db.init_db(conn)
    data = build_dashboard_data(conn)
    data["market_intelligence"] = load_market_intelligence(cfg.root_dir / "market_intelligence")
    data["daytrade"] = recent_dashboard(connect_daytrade(cfg.data_dir / "daytrade.db"))
    write_dashboard_files(data, output_path)
    print(f"[manager] wrote {output_path}")


if __name__ == "__main__":
    main()
