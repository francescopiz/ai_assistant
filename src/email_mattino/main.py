from datetime import datetime
import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

from services.meteo_service import get_forecast_24h
from email_mattino.notizie_scraper import estrai_notizie_grezze
from email_mattino.report_generator import genera_report_html

from services.salute_service import get_report_salute_ieri

load_dotenv()
EMAIL_MITTENTE = os.environ.get("EMAIL_USER")
PASSWORD_APP = os.environ.get("EMAIL_PASS")
EMAIL_DESTINATARIO = os.environ.get("EMAIL_DESTINATARIO")


def build_html_table_rows(meteo_data) -> str:
    """Genera le righe della tabella HTML partendo dai dati del meteo."""
    if not meteo_data:
        return ""
    rows = ""
    for i, info in enumerate(meteo_data):
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
    return rows


def build_salute_html_cards(salute_data) -> str:
    """Genera i box visivi con i dati della salute in chiaro."""
    if not salute_data:
        return "<p style='color:#777;'>Dati salute non pervenuti per questa giornata.</p>"

    colore_passi = "#2b8a3e" if isinstance(salute_data['passi'], int) and salute_data['passi'] >= 10000 else "#e67e22"

    return f"""
    <h2 style="color: #333333; font-size: 18px; border-bottom: 2px solid #2b8a3e; padding-bottom: 5px; margin-top: 25px;">📊 Ultimi Dati Salute Disponibili ({salute_data['data']})</h2>
    <div style="margin-bottom: 20px;">
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
            <tr style="background-color: #f8f9fa;">
                <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>👣 Passi Totali:</strong></td>
                <td style="padding: 10px; border: 1px solid #dee2e6; color: {colore_passi}; font-weight: bold;">{salute_data['passi']}</td>
                <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>😴 Riposo Notturno:</strong></td>
                <td style="padding: 10px; border: 1px solid #dee2e6; color: #206bc4; font-weight: bold;">{salute_data['sonno_ore']}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>❤️ Battito Medio:</strong></td>
                <td style="padding: 10px; border: 1px solid #dee2e6;">{salute_data['battito_medio']} (Min: {salute_data['battito_min']})</td>
                <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>🩸 Ossigeno (SpO2):</strong></td>
                <td style="padding: 10px; border: 1px solid #dee2e6;">{salute_data['ossigeno_medio']}</td>
            </tr>
            <tr style="background-color: #f8f9fa;">
                <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>🔥 Calorie Attive:</strong></td>
                <td style="padding: 10px; border: 1px solid #dee2e6;">{salute_data['calorie_attive']} kcal</td>
                <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>📏 Distanza:</strong></td>
                <td style="padding: 10px; border: 1px solid #dee2e6;">{round(salute_data['distanza_metri'] / 1000, 2)} km</td>
            </tr>
        </table>
    </div>
    """


def build_email_template(table_rows: str, report_intelligente_html: str, salute_in_chiaro_html: str) -> str:
    """Inserisce i blocchi generati dentro il layout responsive finale della mail."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border: 1px solid #e0e0e0;">

            <div style="background: linear-gradient(135deg, #4da7f7 0%, #206bc4 100%); padding: 25px; text-align: center; color: white;">
                <h1 style="margin: 0; font-size: 22px;">Buongiorno Francesco</h1>
                <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 14px;">Il tuo briefing integrato del {datetime.now().strftime('%d/%m/%Y')}</p>
            </div>

            <div style="padding: 20px;">
                <h2 style="color: #333333; font-size: 18px; margin-top: 0; border-bottom: 2px solid #4da7f7; padding-bottom: 5px;">🌤️ Previsioni Meteo (24h)</h2>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                    <thead>
                        <tr style="background-color: #f1f3f5; border-bottom: 2px solid #dee2e6;">
                            <th style="padding: 12px; font-size: 14px; color: #495057;">🕒 Ora</th>
                            <th style="padding: 12px; font-size: 14px; color: #495057;">🌡️ Temp</th>
                            <th style="padding: 12px; font-size: 14px; color: #495057;">💧 Umidità</th>
                            <th style="padding: 12px; font-size: 14px; color: #495057;">🌧️ Pioggia</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>

                {salute_in_chiaro_html}

                <div style="color: #444444; line-height: 1.6; font-size: 15px;">
                    {report_intelligente_html}
                </div>
            </div>

            <div style="background-color: #f8f9fa; padding: 15px; text-align: center; font-size: 12px; color: #777777; border-top: 1px solid #e0e0e0;">
                Chattino ti augura una buona giornata.
            </div>
        </div>
    </body>
    </html>
    """


def send_daily_briefing():
    # Nota: La sincronizzazione da Drive automatica è stata rimossa per via del file sovrascritto.
    # Se vuoi rimetterla, dovrai ricreare un file src/sincronizza_drive.py con lo script iniziale.
    print("ℹ️ Lettura dati dal database locale esistente...")

    print("Recupero informazioni meteo...")
    dati_meteo = get_forecast_24h()
    righe_meteo = build_html_table_rows(dati_meteo) if dati_meteo else ""

    print("Recupero dati reali della salute...")
    # Questa funzione leggerà l'ultima data disponibile nel file .db
    dati_salute = get_report_salute_ieri()
    salute_in_chiaro_html = build_salute_html_cards(dati_salute)

    print("Scraping feed RSS in corso...")
    notizie_grezze = estrai_notizie_grezze()

    print("Generazione report con Ollama (Analisi salute + Notizie)...")
    report_intelligente_html = genera_report_html(notizie_grezze, dati_salute)

    print("DEBUG: Costruzione del template HTML...")
    corpo_html = build_email_template(righe_meteo, report_intelligente_html, salute_in_chiaro_html)

    print(f"DEBUG: Verifica credenziali -> Mittente: {EMAIL_MITTENTE}, DestinatARIO: {EMAIL_DESTINATARIO}")
    if not EMAIL_MITTENTE or not EMAIL_DESTINATARIO:
        print("❌ ERRORE CRITICO: EMAIL_USER o EMAIL_DESTINATARIO non configurati nel file .env!")
        return

    print("DEBUG: Creazione dell'oggetto EmailMessage...")
    msg = EmailMessage()
    msg['Subject'] = f"Briefing Quotidiano - {datetime.now().strftime('%d/%m/%Y')}"
    msg['From'] = EMAIL_MITTENTE
    msg['To'] = EMAIL_DESTINATARIO

    msg.set_content("Attiva la visualizzazione HTML per vedere questo report.")
    msg.add_alternative(corpo_html, subtype='html')

    try:
        print("Connessione al server SMTP e invio email...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            print("DEBUG: Tentativo di login SMTP...")
            smtp.login(EMAIL_MITTENTE, PASSWORD_APP)
            print("DEBUG: Login effettuato. Invio del messaggio...")
            smtp.send_message(msg)
        print("Email inviata con successo!")
    except Exception as e:
        print(f"❌ Errore durante l'invio dell'email: {e}")


if __name__ == "__main__":
    send_daily_briefing()