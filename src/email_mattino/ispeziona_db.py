import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CURRENT_DIR.parent if CURRENT_DIR.name in ["src", "services"] else CURRENT_DIR
DB_PATH = PROJECT_DIR / 'data' / 'health_connect_export.db'


def epoch_days_to_date(days):
    """Converte i giorni Epoch in una data leggibile."""
    epoch = datetime(1970, 1, 1)
    return (epoch + timedelta(days=int(days))).strftime('%d/%m/%Y')


def ispeziona_database():
    if not DB_PATH.exists():
        print(f"❌ Database non trovato in: {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Elenco delle tabelle che stai usando nel tuo script
    tabelle = [
        "steps_record_table",
        "sleep_session_record_table",
        "heart_rate_record_table",
        "heart_rate_record_series_table",
        "oxygen_saturation_record_table",
        "active_calories_burned_record_table",
        "distance_record_table"
    ]

    print("=== ISPEZIONE DATABASE SALUTE ===")

    for tabella in tabelle:
        try:
            # 1. Conta i record totali
            cursor.execute(f"SELECT COUNT(*) FROM {tabella}")
            totale_record = cursor.fetchone()[0]

            if totale_record == 0:
                print(f"⚠ {tabella}: vuota (0 record)")
                continue

            # 2. Prende la data più vecchia e più recente (se esiste la colonna local_date)
            # Nota: heart_rate_record_series_table non ha local_date direttamente, usa parent_key
            if tabella == "heart_rate_record_series_table":
                print(f"✅ {tabella}: {totale_record} record presenti (collegati alla tabella principale)")
                continue

            cursor.execute(f"SELECT MIN(local_date), MAX(local_date) FROM {tabella}")
            min_date, max_date = cursor.fetchone()

            if min_date is not None and max_date is not None:
                data_inizio = epoch_days_to_date(min_date)
                data_fine = epoch_days_to_date(max_date)
                print(f"✅ {tabella}: {totale_record} record | Intervallo date: da {data_inizio} a {data_fine}")
            else:
                print(f"✅ {tabella}: {totale_record} record presenti (colonna data assente o vuota)")

        except sqlite3.OperationalError:
            print(f"❌ La tabella '{tabella}' NON ESISTE nel database corrente!")

    conn.close()


if __name__ == "__main__":
    ispeziona_database()