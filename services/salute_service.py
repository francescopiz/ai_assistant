import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CURRENT_DIR.parent if CURRENT_DIR.name in ["src", "services"] else CURRENT_DIR
DB_PATH = PROJECT_DIR / 'data' / 'health_connect_export.db'


def data_to_epoch_days(date_obj):
    """Converte un oggetto datetime nel numero di giorni dall'Epoca Unix (1/1/1970)."""
    epoch = datetime(1970, 1, 1).date()
    return (date_obj.date() - epoch).days


def get_report_salute_ieri():
    """Estrae i KPI reali della salute per l'ultimo giorno disponibile nel DB."""
    if not DB_PATH.exists():
        print(f"⚠ Database salute non trovato in: {DB_PATH}")
        return None

    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        # 1. CERCA L'ULTIMO GIORNO DISPONIBILE NEL DATABASE (basato sui passi)
        cursor.execute("SELECT MAX(local_date) FROM steps_record_table")
        ultimo_giorno_epoch = cursor.fetchone()[0]

        if not ultimo_giorno_epoch:
            print("⚠ Nessun dato presente nella tabella steps_record_table.")
            conn.close()
            return None

        # Convertiamo i giorni Epoch nella data reale per il report
        epoch = datetime(1970, 1, 1).date()
        giorno_disponibile_dt = epoch + timedelta(days=int(ultimo_giorno_epoch))

        # Inizializzazione struttura dati con la data dinamica trovata
        report = {
            "data": giorno_disponibile_dt.strftime('%d/%m/%Y'),  # Questa stringa andrà nella mail
            "passi": 0,
            "sonno_ore": "N/D",
            "sonno_minuti_totali": 0,
            "battito_medio": "N/D",
            "battito_min": "N/D",
            "battito_max": "N/D",
            "ossigeno_medio": "N/D",
            "calorie_attive": 0,
            "distanza_metri": 0
        }

        # Usiamo 'ultimo_giorno_epoch' al posto di 'ieri_epoch_days' in tutte le query

        # 1. PASSI
        cursor.execute("SELECT SUM(count) FROM steps_record_table WHERE local_date = ?", (ultimo_giorno_epoch,))
        res_passi = cursor.fetchone()[0]
        if res_passi:
            report["passi"] = int(res_passi)

        # 2. SONNO
        cursor.execute(
            "SELECT SUM(end_time - start_time) FROM sleep_session_record_table WHERE local_date = ?",
            (ultimo_giorno_epoch,)
        )
        res_sonno_ms = cursor.fetchone()[0]
        if res_sonno_ms:
            minuti_totali = res_sonno_ms / 1000 / 60
            report["sonno_minuti_totali"] = int(minuti_totali)
            ore = minuti_totali // 60
            minuti = minuti_totali % 60
            report["sonno_ore"] = f"{int(ore)}h {int(minuti)}m"

        # 3. BATTITO CARDIACO
        cursor.execute("""
                       SELECT AVG(beats_per_minute), MIN(beats_per_minute), MAX(beats_per_minute)
                       FROM heart_rate_record_series_table
                       WHERE parent_key IN (SELECT row_id FROM heart_rate_record_table WHERE local_date = ?)
                       """, (ultimo_giorno_epoch,))
        res_battito = cursor.fetchone()
        if res_battito and res_battito[0] is not None:
            report["battito_medio"] = f"{int(res_battito[0])} BPM"
            report["battito_min"] = f"{int(res_battito[1])} BPM"
            report["battito_max"] = f"{int(res_battito[2])} BPM"

        # 4. OSSIGENAZIONE
        cursor.execute("SELECT AVG(percentage) FROM oxygen_saturation_record_table WHERE local_date = ?",
                       (ultimo_giorno_epoch,))
        res_spo2 = cursor.fetchone()[0]
        if res_spo2:
            report["ossigeno_medio"] = f"{round(res_spo2, 1)}%"

        # 5. CALORIE ATTIVE BRUCIATE
        cursor.execute("SELECT SUM(energy) FROM active_calories_burned_record_table WHERE local_date = ?",
                       (ultimo_giorno_epoch,))
        res_cal = cursor.fetchone()[0]
        if res_cal:
            report["calorie_attive"] = int(res_cal / 1000) if res_cal > 50000 else int(res_cal)

        # 6. DISTANZA TOTALE (Metri)
        cursor.execute("SELECT SUM(distance) FROM distance_record_table WHERE local_date = ?", (ultimo_giorno_epoch,))
        res_dist = cursor.fetchone()[0]
        if res_dist:
            report["distanza_metri"] = int(res_dist)

        conn.close()
        return report

    except Exception as e:
        print(f"❌ Errore durante l'estrazione dei dati salute reali: {e}")
        return None


if __name__ == "__main__":
    print("🧪 Test di estrazione dati reali dal database...")
    import pprint

    pprint.pprint(get_report_salute_ieri())
