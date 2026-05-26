from datetime import datetime
import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

from services.meteo_service import get_forecast_24h

load_dotenv()
EMAIL_MITTENTE = os.environ.get("EMAIL_USER")
PASSWORD_APP = os.environ.get("EMAIL_PASS")


def build_html_table_rows(meteo_data):
    """Genera le righe della tabella HTML partendo dai dati del meteo."""
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


def build_email_template(table_rows):
    """Inserisce le righe generate dentro il template HTML principale."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border: 1px solid #e0e0e0;">
            <div style="background: linear-gradient(135deg, #4da7f7 0%, #206bc4 100%); padding: 25px; text-align: center; color: white;">
                <h1 style="margin: 0; font-size: 22px;">Meteo di oggi</h1>
            </div>
            <div style="padding: 20px;">
                <table style="width: 100%; border-collapse: collapse;">
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
            </div>
        </div>
    </body>
    </html>
    """


def send_weather_email():
    """Funzione principale orchestratrice."""
    dati_meteo = get_forecast_24h()
    if not dati_meteo:
        print("Impossibile procedere con l'invio: dati meteo non disponibili.")
        return

    righe_html = build_html_table_rows(dati_meteo)
    corpo_html = build_email_template(righe_html)

    msg = EmailMessage()
    msg['Subject'] = f"Aggiornamento del {datetime.now().strftime('%d/%m/%Y')}"
    msg['From'] = EMAIL_MITTENTE
    msg['To'] = 'francy.pizzuto@gmail.com'

    msg.set_content("Attiva la visualizzazione HTML per vedere questo report.")
    msg.add_alternative(corpo_html, subtype='html')

    try:
        print("Connessione al server SMTP e invio email...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_MITTENTE, PASSWORD_APP)
            smtp.send_message(msg)
        print("Email inviata con successo!")
    except Exception as e:
        print(f"Errore durante l'invio dell'email: {e}")


if __name__ == "__main__":
    send_weather_email()
