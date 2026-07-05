import os
import smtplib
import re
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from services.database import SessionLocal, EmailConfig, get_preference, ScheduledTaskLog
from services.meteo_service import get_forecast_24h
from src.email_mattino.notizie_scraper import estrai_notizie_grezze
from src.email_mattino.report_generator import genera_report_html
from services.salute_service import get_report_salute_ieri, DB_PATH

# Scheduler instance
scheduler = BackgroundScheduler()

def get_email_credentials():
    return {
        "user": os.environ.get("EMAIL_USER", get_preference("EMAIL_USER")),
        "pass": os.environ.get("EMAIL_PASS", get_preference("EMAIL_PASS")),
        "dest": os.environ.get("EMAIL_DESTINATARIO", get_preference("EMAIL_DESTINATARIO"))
    }

def get_report_salute_comparison():
    """
    Raccoglie i dati salute dell'ultimo giorno e del giorno precedente per calcolare il delta.
    Se il database non esiste, genera dati mock per i test.
    """
    import sqlite3
    
    if not DB_PATH.exists():
        # Fallback Mock data
        ieri = {
            "data": (datetime.now() - timedelta(days=1)).strftime('%d/%m/%Y'),
            "passi": 8450,
            "sonno_ore": "7h 15m",
            "sonno_minuti_totali": 435,
            "battito_medio": "68 BPM",
            "battito_min": "54 BPM",
            "battito_max": "110 BPM",
            "ossigeno_medio": "98%",
            "calorie_attive": 350,
            "distanza_metri": 6100
        }
        altro_ieri = {
            "data": (datetime.now() - timedelta(days=2)).strftime('%d/%m/%Y'),
            "passi": 9400,
            "sonno_ore": "8h 00m",
            "sonno_minuti_totali": 480,
            "battito_medio": "66 BPM",
            "battito_min": "52 BPM",
            "battito_max": "115 BPM",
            "ossigeno_medio": "98%",
            "calorie_attive": 400,
            "distanza_metri": 6800
        }
        return ieri, altro_ieri, True
        
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Cerca gli ultimi due giorni disponibili nei passi
        cursor.execute("SELECT DISTINCT local_date FROM steps_record_table ORDER BY local_date DESC LIMIT 2")
        rows = cursor.fetchall()
        
        if len(rows) < 2:
            # Not enough data, return latest with empty previous day
            ieri = get_report_salute_ieri()
            return ieri, None, False
            
        ultimo_epoch = rows[0][0]
        penultimo_epoch = rows[1][0]
        
        # Helper to query for an epoch
        def get_data_for_epoch(epoch_val):
            epoch = datetime(1970, 1, 1).date()
            giorno_dt = epoch + timedelta(days=int(epoch_val))
            
            rep = {
                "data": giorno_dt.strftime('%d/%m/%Y'),
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
            
            # PASSI
            cursor.execute("SELECT SUM(count) FROM steps_record_table WHERE local_date = ?", (epoch_val,))
            res = cursor.fetchone()[0]
            if res: rep["passi"] = int(res)
            
            # SONNO
            cursor.execute("SELECT SUM(end_time - start_time) FROM sleep_session_record_table WHERE local_date = ?", (epoch_val,))
            res = cursor.fetchone()[0]
            if res:
                tot_min = res / 1000 / 60
                rep["sonno_minuti_totali"] = int(tot_min)
                rep["sonno_ore"] = f"{int(tot_min // 60)}h {int(tot_min % 60)}m"
                
            # BATTITO
            cursor.execute("""
                           SELECT AVG(beats_per_minute), MIN(beats_per_minute), MAX(beats_per_minute)
                           FROM heart_rate_record_series_table
                           WHERE parent_key IN (SELECT row_id FROM heart_rate_record_table WHERE local_date = ?)
                           """, (epoch_val,))
            res = cursor.fetchone()
            if res and res[0] is not None:
                rep["battito_medio"] = f"{int(res[0])} BPM"
                rep["battito_min"] = f"{int(res[1])} BPM"
                rep["battito_max"] = f"{int(res[2])} BPM"
                
            # OSSIGENO
            cursor.execute("SELECT AVG(percentage) FROM oxygen_saturation_record_table WHERE local_date = ?", (epoch_val,))
            res = cursor.fetchone()[0]
            if res: rep["ossigeno_medio"] = f"{round(res, 1)}%"
            
            # CALORIE
            cursor.execute("SELECT SUM(energy) FROM active_calories_burned_record_table WHERE local_date = ?", (epoch_val,))
            res = cursor.fetchone()[0]
            if res: rep["calorie_attive"] = int(res / 1000) if res > 50000 else int(res)
            
            # DISTANZA
            cursor.execute("SELECT SUM(distance) FROM distance_record_table WHERE local_date = ?", (epoch_val,))
            res = cursor.fetchone()[0]
            if res: rep["distanza_metri"] = int(res)
            
            return rep
            
        ieri = get_data_for_epoch(ultimo_epoch)
        altro_ieri = get_data_for_epoch(penultimo_epoch)
        conn.close()
        return ieri, altro_ieri, False
        
    except Exception as e:
        print(f"Errore calcolo delta salute: {e}")
        return None, None, False

def extract_action_items_from_transcripts() -> list:
    """Scansiona data/raw_sources per estrarrre i to-do vocali recenti."""
    raw_path = Path(get_preference("RAW_SOURCES_PATH", str(Path(__file__).resolve().parent.parent / "data" / "raw_sources")))
    action_items = []
    
    # Scansiona file di trascrizione degli ultimi 7 giorni
    now = datetime.now()
    if not raw_path.exists():
        return action_items
        
    for file in raw_path.glob("*.txt"):
        mtime = datetime.fromtimestamp(file.stat().st_mtime)
        if now - mtime < timedelta(days=7):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()
                # Trova frasi tipo "devo ricordarmi di", "ricordarsi di", "da fare"
                sentences = re.split(r'[.!?\n]', content)
                for s in sentences:
                    s_clean = s.strip()
                    if not s_clean:
                        continue
                    if any(trigger in s_clean.lower() for trigger in ["devo ricordarmi di", "ricorda di", "ricordati di", "da fare", "task:"]):
                        action_items.append(f"{s_clean} (da nota audio del {mtime.strftime('%d/%m')})")
            except Exception:
                continue
    return action_items

def get_on_this_day_note() -> dict:
    """Verifica se esiste una nota di diario di un mese fa o un anno fa."""
    wiki_path = Path(get_preference("WIKI_PATH", str(Path(__file__).resolve().parent.parent / "data" / "wiki")))
    today = datetime.now()
    
    dates_to_check = {
        "1 mese fa": today - timedelta(days=30),
        "1 anno fa": today - timedelta(days=365)
    }
    
    for label, target_date in dates_to_check.items():
        filename = target_date.strftime("%Y-%m-%d.md")
        filepath = wiki_path / filename
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                return {"label": label, "date": target_date.strftime('%d/%m/%Y'), "content": content, "filename": filename}
            except Exception:
                continue
    return None

def check_wiki_linting() -> dict:
    """Esegue un linting di base della Wiki per trovare pagine orfane o con placeholder."""
    wiki_path = Path(get_preference("WIKI_PATH", str(Path(__file__).resolve().parent.parent / "data" / "wiki")))
    index_file = wiki_path / "index.md"
    
    orphans = []
    placeholders = []
    
    if not wiki_path.exists():
        return {"orphans": [], "placeholders": []}
        
    all_files = [f[:-3] for f in os.listdir(wiki_path) if f.endswith(".md") and f not in ["log.md", "WIKI_SCHEMA.md"]]
    
    # Read index content
    index_content = ""
    if index_file.exists():
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                index_content = f.read()
        except Exception:
            pass
            
    for page in all_files:
        if page == "index":
            continue
        # Check if orphaned
        if f"[[{page}]]" not in index_content:
            # Scansiona altre note per vedere se è collegata da qualche parte
            linked = False
            for other in all_files:
                if other == page or other == "index":
                    continue
                try:
                    with open(wiki_path / f"{other}.md", "r", encoding="utf-8") as f:
                        if f"[[{page}]]" in f.read():
                            linked = True
                            break
                except Exception:
                    continue
            if not linked:
                orphans.append(page)
                
        # Check for placeholders or missing info
        try:
            with open(wiki_path / f"{page}.md", "r", encoding="utf-8") as f:
                content = f.read()
                if "N/D" in content or "Non rilevato" in content or "TODO" in content:
                    placeholders.append(page)
        except Exception:
            continue
            
    return {"orphans": orphans, "placeholders": placeholders}

def compile_morning_email(modules_list: list) -> str:
    """Compila il corpo HTML dell'email in base ai moduli attivi."""
    now_str = datetime.now().strftime('%d/%m/%Y')
    
    # METEO
    meteo_html = ""
    if "weather" in modules_list:
        try:
            dati_meteo = get_forecast_24h()
            if dati_meteo:
                rows = ""
                for i, info in enumerate(dati_meteo[:8]): # Mostra solo i prossimi 8 slot orari per compattezza
                    bg_color = "#ffffff" if i % 2 == 0 else "#f8f9fa"
                    stile_pioggia = "color: #dc3545; font-weight: bold;" if info['prob_pioggia'] > 40 else "color: #333333;"
                    rows += f"""
                    <tr style="background-color: {bg_color}; text-align: center; border-bottom: 1px solid #dddddd;">
                        <td style="padding: 10px; font-weight: bold; color: #555555;">{info['ora']}</td>
                        <td style="padding: 10px; color: #ff6b6b; font-weight: bold;">{info['temperatura']}</td>
                        <td style="padding: 10px; color: #4dadf7;">{info['umidita']}</td>
                        <td style="padding: 10px; {stile_pioggia}">{info['prob_pioggia_str']}</td>
                    </tr>
                    """
                meteo_html = f"""
                <h2 style="color: #206bc4; font-size: 18px; border-bottom: 2px solid #4da7f7; padding-bottom: 5px; margin-top: 25px;">🌤️ Previsioni Meteo (Prossime ore)</h2>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 14px;">
                    <thead>
                        <tr style="background-color: #f1f3f5; border-bottom: 2px solid #dee2e6;">
                            <th style="padding: 10px; color: #495057;">🕒 Ora</th>
                            <th style="padding: 10px; color: #495057;">🌡️ Temp</th>
                            <th style="padding: 10px; color: #495057;">💧 Umidità</th>
                            <th style="padding: 10px; color: #495057;">🌧️ Pioggia</th>
                        </tr>
                    </thead>
                    <tbody>{rows}</tbody>
                </table>
                """
        except Exception as e:
            meteo_html = f"<p style='color: red;'>Errore recupero meteo: {e}</p>"

    # SALUTE E DELTA
    salute_html = ""
    dati_ieri = None
    if "health" in modules_list:
        ieri, altro_ieri, is_mock = get_report_salute_comparison()
        dati_ieri = ieri
        if ieri:
            colore_passi = "#2b8a3e" if ieri['passi'] >= 10000 else "#e67e22"
            
            # Calcolo delta se c'è altro_ieri
            delta_passi_str = ""
            delta_sonno_str = ""
            if altro_ieri:
                # Passi delta
                diff_passi = ieri['passi'] - altro_ieri['passi']
                pct_passi = (diff_passi / max(1, altro_ieri['passi'])) * 100
                segno_passi = "+" if diff_passi >= 0 else ""
                colore_d_passi = "#2b8a3e" if diff_passi >= 0 else "#dc3545"
                delta_passi_str = f" <span style='font-size:12px; color:{colore_d_passi}; font-weight:normal;'>({segno_passi}{int(pct_passi)}% rispetto a ieri)</span>"
                
                # Sonno delta
                diff_sonno = ieri['sonno_minuti_totali'] - altro_ieri['sonno_minuti_totali']
                pct_sonno = (diff_sonno / max(1, altro_ieri['sonno_minuti_totali'])) * 100
                segno_sonno = "+" if diff_sonno >= 0 else ""
                colore_d_sonno = "#2b8a3e" if diff_sonno >= 0 else "#dc3545"
                delta_sonno_str = f" <span style='font-size:12px; color:{colore_d_sonno}; font-weight:normal;'>({segno_sonno}{int(pct_sonno)}% rispetto a ieri)</span>"

            info_mock = " <span style='color: #888; font-size:11px;'>(Dati simulati per test)</span>" if is_mock else ""
            salute_html = f"""
            <h2 style="color: #2b8a3e; font-size: 18px; border-bottom: 2px solid #2b8a3e; padding-bottom: 5px; margin-top: 25px;">📊 KPI Salute di Ieri ({ieri['data']}){info_mock}</h2>
            <table style="width: 100%; border-collapse: collapse; font-size: 14px; margin-bottom: 20px;">
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>👣 Passi Totali:</strong></td>
                    <td style="padding: 10px; border: 1px solid #dee2e6; color: {colore_passi}; font-weight: bold;">{ieri['passi']}{delta_passi_str}</td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>😴 Riposo Notturno:</strong></td>
                    <td style="padding: 10px; border: 1px solid #dee2e6; color: #206bc4; font-weight: bold;">{ieri['sonno_ore']}{delta_sonno_str}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>❤️ Battito Medio:</strong></td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;">{ieri['battito_medio']} (Min: {ieri['battito_min']})</td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>🩸 Ossigeno (SpO2):</strong></td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;">{ieri['ossigeno_medio']}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>🔥 Calorie Attive:</strong></td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;">{ieri['calorie_attive']} kcal</td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>📏 Distanza:</strong></td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;">{round(ieri['distanza_metri'] / 1000, 2)} km</td>
                </tr>
            </table>
            """

    # NOTIZIE & AI REPORT
    notizie_html = ""
    if "news" in modules_list:
        try:
            notizie_grezze = estrai_notizie_grezze()
            # Se siamo senza LLM/Ollama, generiamo una sintesi formattata pulita delle notizie per evitare crash
            try:
                # Prova a usare Ollama
                report_ai = genera_report_html(notizie_grezze, dati_ieri)
                notizie_html = f"""
                <div style="background-color: #fff; padding: 15px; border-left: 4px solid #206bc4; margin-bottom: 20px;">
                    {report_ai}
                </div>
                """
            except Exception:
                # Fallback sintesi notizie semplice
                notizie_html = f"""
                <h2 style="color: #206bc4; font-size: 18px; border-bottom: 2px solid #4da7f7; padding-bottom: 5px; margin-top: 25px;">📰 Rassegna Stampa Quotidiana</h2>
                <div style="font-size: 14px; line-height: 1.5;">
                    <p><em>Impossibile contattare l'LLM locale. Ecco una panoramica testuale estratta dai feed:</em></p>
                    <pre style="white-space: pre-wrap; background: #f8f9fa; padding: 10px; font-family: sans-serif; font-size: 13px;">{notizie_grezze[:1200]}...</pre>
                </div>
                """
        except Exception as e:
            notizie_html = f"<p style='color: red;'>Errore rassegna stampa: {e}</p>"

    # ON THIS DAY
    on_this_day_html = ""
    if "on_this_day" in modules_list:
        otd = get_on_this_day_note()
        if otd:
            # Fallback a testo senza LLM
            on_this_day_html = f"""
            <h2 style="color: #e67e22; font-size: 18px; border-bottom: 2px solid #e67e22; padding-bottom: 5px; margin-top: 25px;">⏳ Accadde Oggi ({otd['label']} - {otd['date']})</h2>
            <div style="background-color: #fffbeb; padding: 15px; border-radius: 6px; border: 1px solid #fef3c7; font-size: 14px; font-style: italic; line-height: 1.5; color: #78350f;">
                <strong>Nota del file [[{otd['filename']}]]:</strong><br>
                {otd['content'][:800].replace('\n', '<br>')}...
            </div>
            """

    # ACTION ITEMS
    action_items_html = ""
    if "action_items" in modules_list:
        items = extract_action_items_from_transcripts()
        if items:
            list_items = "".join(f"<li style='margin-bottom: 6px;'>[ ] {it}</li>" for it in items)
            action_items_html = f"""
            <h2 style="color: #d63384; font-size: 18px; border-bottom: 2px solid #d63384; padding-bottom: 5px; margin-top: 25px;">📌 Action Items Rilevati (Ultimi 7 giorni)</h2>
            <ul style="font-size: 14px; line-height: 1.5; padding-left: 20px; color: #495057;">
                {list_items}
            </ul>
            """

    # WIKI LINTING
    lint_html = ""
    if "wiki_lint" in modules_list:
        lint = check_wiki_linting()
        if lint["orphans"] or lint["placeholders"]:
            orphans_str = ", ".join(f"[[{o}]]" for o in lint["orphans"]) if lint["orphans"] else "Nessuna"
            placeholders_str = ", ".join(f"[[{p}]]" for p in lint["placeholders"]) if lint["placeholders"] else "Nessuna"
            lint_html = f"""
            <h2 style="color: #6f42c1; font-size: 18px; border-bottom: 2px solid #6f42c1; padding-bottom: 5px; margin-top: 25px;">🛠️ Sintesi & Diagnostica Wiki</h2>
            <div style="background-color: #f3e8ff; padding: 12px; border-radius: 6px; font-size: 13px; color: #581c87; line-height: 1.4;">
                <strong>Pagine orfane rilevate:</strong> {orphans_str}<br>
                <strong>Pagine con placeholder (N/D o TODO):</strong> {placeholders_str}<br>
                <p style="margin-top: 8px; font-size: 12px; font-style: italic; color: #6b21a8;">Suggerimento: Aggiorna l'indice o collega le pagine per evitare un Secondo Cervello frammentato.</p>
            </div>
            """

    # TEMPLATE CORPO GENERALE
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border: 1px solid #e0e0e0;">
            <div style="background: linear-gradient(135deg, #4da7f7 0%, #206bc4 100%); padding: 25px; text-align: center; color: white;">
                <h1 style="margin: 0; font-size: 22px;">Buongiorno Francesco</h1>
                <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 14px;">Il tuo briefing integrato del {now_str}</p>
            </div>
            <div style="padding: 20px;">
                {salute_html}
                {meteo_html}
                {notizie_html}
                {on_this_day_html}
                {action_items_html}
                {lint_html}
            </div>
            <div style="background-color: #f8f9fa; padding: 15px; text-align: center; font-size: 12px; color: #777777; border-top: 1px solid #e0e0e0;">
                Secondo Cervello OS • Generato automaticamente alle {datetime.now().strftime('%H:%M:%S')}
            </div>
        </div>
    </body>
    </html>
    """
    return html_body

def compile_evening_email(modules_list: list) -> str:
    """Compila il corpo HTML dell'email serale."""
    now_str = datetime.now().strftime('%d/%m/%Y')
    
    # Esegue solo i moduli necessari per la sera
    salute_html = ""
    if "health" in modules_list:
        ieri, _, is_mock = get_report_salute_comparison()
        if ieri:
            colore_passi = "#2b8a3e" if ieri['passi'] >= 10000 else "#e67e22"
            info_mock = " <span style='color: #888; font-size:11px;'>(Dati simulati)</span>" if is_mock else ""
            salute_html = f"""
            <h2 style="color: #2b8a3e; font-size: 18px; border-bottom: 2px solid #2b8a3e; padding-bottom: 5px; margin-top: 25px;">📊 Riepilogo Biometrico odierno{info_mock}</h2>
            <p>Ecco un riepilogo parziale delle tue metriche registrate fino ad ora:</p>
            <table style="width: 100%; border-collapse: collapse; font-size: 14px; margin-bottom: 20px;">
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>👣 Passi:</strong></td>
                    <td style="padding: 10px; border: 1px solid #dee2e6; color: {colore_passi}; font-weight: bold;">{ieri['passi']}</td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>🔥 Calorie Attive:</strong></td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;">{ieri['calorie_attive']} kcal</td>
                </tr>
            </table>
            """
            
    # ACTION ITEMS
    action_items_html = ""
    if "action_items" in modules_list:
        items = extract_action_items_from_transcripts()
        if items:
            list_items = "".join(f"<li style='margin-bottom: 6px;'>[ ] {it}</li>" for it in items)
            action_items_html = f"""
            <h2 style="color: #d63384; font-size: 18px; border-bottom: 2px solid #d63384; padding-bottom: 5px; margin-top: 25px;">📌 To-Do List ed Action Items pendenti</h2>
            <ul style="font-size: 14px; line-height: 1.5; padding-left: 20px; color: #495057;">
                {list_items}
            </ul>
            """
            
    # LINTING
    lint_html = ""
    if "wiki_lint" in modules_list:
        lint = check_wiki_linting()
        if lint["orphans"] or lint["placeholders"]:
            orphans_str = ", ".join(f"[[{o}]]" for o in lint["orphans"]) if lint["orphans"] else "Nessuna"
            lint_html = f"""
            <h2 style="color: #6f42c1; font-size: 18px; border-bottom: 2px solid #6f42c1; padding-bottom: 5px; margin-top: 25px;">🛠️ Revisione Stato Wiki</h2>
            <p style="font-size: 13px; color: #581c87;">Pagine orfane da riorganizzare: {orphans_str}</p>
            """

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border: 1px solid #e0e0e0;">
            <div style="background: linear-gradient(135deg, #6c757d 0%, #343a40 100%); padding: 25px; text-align: center; color: white;">
                <h1 style="margin: 0; font-size: 22px;">Buonasera Francesco</h1>
                <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 14px;">Il tuo briefing serale del {now_str}</p>
            </div>
            <div style="padding: 20px;">
                {salute_html}
                {action_items_html}
                {lint_html}
            </div>
            <div style="background-color: #f8f9fa; padding: 15px; text-align: center; font-size: 12px; color: #777777; border-top: 1px solid #e0e0e0;">
                Secondo Cervello OS • Generato automaticamente alle {datetime.now().strftime('%H:%M:%S')}
            </div>
        </div>
    </body>
    </html>
    """
    return html_body

def send_scheduled_email(email_type: str):
    """Esegue l'invio effettivo dell'email schedulata in base alla configurazione."""
    print(f"⏰ [Scheduler] Esecuzione invio email: {email_type}")
    
    db = SessionLocal()
    try:
        config = db.query(EmailConfig).filter_by(email_type=email_type).first()
        if not config or not config.enabled:
            print(f"ℹ️ [Scheduler] Email {email_type} disabilitata o non configurata. Salto invio.")
            return
            
        modules = [m.strip() for m in config.active_modules.split(",") if m.strip()]
        
        if email_type == "morning":
            html_body = compile_morning_email(modules)
            subject = f"Briefing Mattutino - {datetime.now().strftime('%d/%m/%Y')}"
        else:
            html_body = compile_evening_email(modules)
            subject = f"Resoconto Serale - {datetime.now().strftime('%d/%m/%Y')}"
            
        # Invio email
        creds = get_email_credentials()
        if not creds["user"] or not creds["dest"]:
            raise ValueError("Credenziali email mancanti (EMAIL_USER o EMAIL_DESTINATARIO non definiti)")
            
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = creds["user"]
        msg['To'] = creds["dest"]
        msg.set_content("Attiva la visualizzazione HTML per vedere questo report.")
        msg.add_alternative(html_body, subtype='html')
        
        # Invia
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(creds["user"], creds["pass"])
            smtp.send_message(msg)
            
        # Aggiorna log di esecuzione nel database
        config.last_run = datetime.utcnow()
        log_entry = ScheduledTaskLog(
            task_name=f"email_{email_type}",
            status="SUCCESS",
            details=f"Email inviata con successo a {creds['dest']} con moduli: {config.active_modules}"
        )
        db.add(log_entry)
        db.commit()
        print(f"✅ [Scheduler] Email {email_type} inviata con successo!")
        
    except Exception as e:
        print(f"❌ [Scheduler] Errore invio email {email_type}: {e}")
        try:
            log_entry = ScheduledTaskLog(
                task_name=f"email_{email_type}",
                status="FAILED",
                details=str(e)
            )
            db.add(log_entry)
            db.commit()
        except Exception as db_err:
            print(f"Errore scrittura log fallimento su DB: {db_err}")
    finally:
        db.close()

def reschedule_email_jobs():
    """
    Rilegge le configurazioni di orario dal database e aggiorna i job dell'APScheduler.
    """
    db = SessionLocal()
    try:
        configs = db.query(EmailConfig).all()
        for config in configs:
            job_id = f"email_{config.email_type}"
            
            # Rimuove il job se già esistente per ricrearlo
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
                
            if config.enabled:
                try:
                    hour, minute = map(int, config.schedule_time.split(":"))
                    trigger = CronTrigger(hour=hour, minute=minute)
                    
                    scheduler.add_job(
                        send_scheduled_email,
                        trigger=trigger,
                        args=[config.email_type],
                        id=job_id,
                        replace_existing=True
                    )
                    print(f"📅 [Scheduler] Schedulata email '{config.email_type}' alle {config.schedule_time}")
                except Exception as parse_err:
                    print(f"❌ [Scheduler] Orario non valido per {config.email_type}: {config.schedule_time} ({parse_err})")
    except Exception as e:
        print(f"❌ [Scheduler] Errore durante il rescheduling: {e}")
    finally:
        db.close()
