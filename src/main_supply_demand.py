from datetime import date

from src import db
from src.config import load_config
from src.jquants_client import JQuantsClient
from src.supply_demand_loader import fetch_or_load_supply_demand


def main() -> None:
    cfg = load_config(); conn = db.connect(cfg.db_path); db.init_db(conn)
    client = JQuantsClient.from_env()
    rows = conn.execute("SELECT code, MAX(event_date) AS event_date FROM recommendations GROUP BY code").fetchall()
    loaded = 0
    for row in rows:
        features, _ = fetch_or_load_supply_demand(row["code"], date.fromisoformat(row["event_date"]), cfg.margin_interest_path, client)
        db.upsert_supply_demand(conn, features); loaded += 1
    conn.commit()
    print(f"[supply-demand] updated={loaded}")


if __name__ == "__main__": main()
