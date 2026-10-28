"""Apply the additive v1 account schema; run before application rollout."""
from .settings import Settings
from .storage import Storage


def main():
    settings = Settings()
    url = settings.resolve_database_url()
    if not url:
        raise SystemExit("Configure DATABASE_URL or DATABASE_URL_FILE first")
    storage = Storage(url)
    try:
        storage.migrate()
        print("Account database schema v1 is ready.")
    finally:
        storage.engine.dispose()


if __name__ == "__main__":
    main()
