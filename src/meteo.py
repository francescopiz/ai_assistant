from datetime import datetime

import requests

LATITUDE = "42.51988404523463"
LONGITUDE = "14.116766654623449"

url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&hourly=temperature_2m,relative_humidity_2m,precipitation_probability&timezone=Europe/Rome"

try:
    response = requests.get(url)
    data = response.json()

    orari = data['hourly']['time']
    temperature = data['hourly']['temperature_2m']
    umidita = data['hourly']['relative_humidity_2m']
    pioggia_prob = data['hourly']['precipitation_probability']

    unita_temp = data['hourly_units']['temperature_2m']
    unita_umidita = data['hourly_units']['relative_humidity_2m']
    unita_pioggia = data['hourly_units']['precipitation_probability']

    for i in range(24):
        ora_formattata = datetime.fromisoformat(orari[i]).strftime("%H:%M")
        temp = temperature[i]
        umi = umidita[i]
        prob_p = pioggia_prob[i]

        print(
            f"Ore {ora_formattata} -> Temp: {temp}{unita_temp} | Umidità: {umi}{unita_umidita} | Prob. Pioggia: {prob_p}{unita_pioggia}")

except Exception as e:
    print(f"Errore nel recupero dei dati: {e}")
