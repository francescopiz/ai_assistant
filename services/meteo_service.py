from datetime import datetime
import requests

LATITUDE = "42.51988404523463"
LONGITUDE = "14.116766654623449"
URL_API = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&hourly=temperature_2m,relative_humidity_2m,precipitation_probability&timezone=Europe/Rome"


def get_forecast_24h():
    """
    Recupera le previsioni meteo esclusivamente per le PROSSIME 24 ore
    rispetto al momento esatto dell'esecuzione.
    """
    try:
        response = requests.get(URL_API)
        response.raise_for_status()
        data = response.json()

        units = {
            "temp": data['hourly_units']['temperature_2m'],
            "umi": data['hourly_units']['relative_humidity_2m'],
            "pioggia": data['hourly_units']['precipitation_probability']
        }

        orari = data['hourly']['time']
        temperature = data['hourly']['temperature_2m']
        umidita = data['hourly']['relative_humidity_2m']
        pioggia_prob = data['hourly']['precipitation_probability']

        # 1. Troviamo il momento attuale (arrotondato all'ora corrente)
        ora_attuale_iso = datetime.now().strftime("%Y-%m-%dT%H:00")

        # 2. Cerchiamo l'indice di quest'ora all'interno dei dati dell'API
        # Se non lo trova, partiamo da 0 come fallback
        indice_partenza = 0
        for idx, timestamp in enumerate(orari):
            if timestamp.startswith(ora_attuale_iso):
                indice_partenza = idx
                break

        report_meteo = []

        # 3. Prendiamo i 24 slot orari partendo da ORA in poi
        for i in range(indice_partenza, indice_partenza + 24):
            # Evitiamo di andare fuori dai limiti della lista se siamo a fine previsione
            if i >= len(orari):
                break

            ora_formattata = datetime.fromisoformat(orari[i]).strftime("%H:%M")

            dati_ora = {
                "ora": ora_formattata,
                "temperatura": f"{temperature[i]}{units['temp']}",
                "umidita": f"{umidita[i]}{units['umi']}",
                "prob_pioggia": pioggia_prob[i],
                "prob_pioggia_str": f"{pioggia_prob[i]}{units['pioggia']}"
            }
            report_meteo.append(dati_ora)

        return report_meteo

    except Exception as e:
        print(f"Errore: {e}")
        return []

    except requests.RequestException as e:
        print(f"Errore di rete durante il recupero del meteo: {e}")
        return []
    except KeyError as e:
        print(f"Errore nel parsing dei dati JSON: manca la chiave {e}")
        return []