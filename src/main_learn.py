from src import db
from src.adaptive_learner import train_profile, write_profile
from src.config import load_config


def main() -> None:
    cfg = load_config(); conn = db.connect(cfg.db_path); db.init_db(conn)
    profile = train_profile(conn, cfg.rules)
    write_profile(profile, cfg.learning_profile_path); db.insert_learning_run(conn, profile); conn.commit()
    print(f"[learn] status={profile['status']} samples={profile['sample_count']} {profile['message']}")


if __name__ == "__main__": main()
