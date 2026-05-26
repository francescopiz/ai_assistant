import os
import ollama

MODELLO_LLM = os.environ.get("OLLAMA_MODEL", "gemma4:26b")


def genera_report_html(notizie_grezze: str, dati_salute_grezzi: dict) -> str:
    """Interroga Ollama per sintetizzare notizie e analizzare i trend della salute in formato HTML."""

    # Formattazione testuale pulita dei dati di salute da iniettare nel prompt dell'AI
    contesto_salute = "Nessun dato salute disponibile per ieri."
    if dati_salute_grezzi:
        contesto_salute = (
            f"Dati biometrici registrati nella giornata di ieri ({dati_salute_grezzi['data']}):\n"
            f"- Passi effettuati: {dati_salute_grezzi['passi']}\n"
            f"- Durata del sonno: {dati_salute_grezzi['sonno_ore']}\n"
            f"- Frequenza cardiaca: Media {dati_salute_grezzi['battito_medio']} (Min: {dati_salute_grezzi['battito_min']}, Max: {dati_salute_grezzi['battito_max']})\n"
            f"- Livello ossigeno medio (SpO2): {dati_salute_grezzi['ossigeno_medio']}\n"
            f"- Calorie attive bruciate: {dati_salute_grezzi['calorie_attive']} kcal\n"
            f"- Distanza percorsa: {dati_salute_grezzi['distanza_metri']} metri\n"
        )

    prompt_sistema = (
        "Sei un assistente AI d'élite, caporedattore e life-coach biologico personale.\n"
        "Il tuo compito è analizzare le informazioni del mattino e i dati biometrici dell'utente per generare un briefing unico.\n\n"
        "REGOLE DI GENERAZIONE:\n"
        "1. Crea una sezione iniziale intitolata '🧠 Bio-Insights & Consigli di Vita'. Analizza le metriche della salute di ieri, mettile in relazione (es. impatto del sonno sul battito o sull'attività) e offri 2 consigli pratici e personalizzati per la giornata che inizia.\n"
        "2. Crea una seconda sezione intitolata '📰 Il Punto sulle Notizie Mondiali'. Dividi le notizie in massimo 3 macro-categorie pulite.\n"
        "3. REGOLE DI FORMATTAZIONE: Rispondi USANDO ESCLUSIVAMENTE tag HTML validi corporei (es: <h3>, <p>, <ul>, <li>, <strong>). NON usare blocchi di codice markdown (```html ). Scrivi testo HTML puro.\n"
        "4. I link esterni devono avere questo stile grafico: style='color: #206bc4; text-decoration: none;'"
    )

    prompt_utente = (
        f"Ecco il resoconto biologico di ieri:\n{contesto_salute}\n\n"
        f"Ecco le notizie grezze raccolte dai feed RSS:\n\n{notizie_grezze}"
    )

    try:
        ollama_host = os.environ.get("OLLAMA_HOST", "[http://127.0.0.1:11434](http://127.0.0.1:11434)")
        if "0.0.0.0" in ollama_host:
            ollama_host = ollama_host.replace("0.0.0.0", "127.0.0.1")
        if not ollama_host.startswith("http"):
            ollama_host = "http://" + ollama_host

        client = ollama.Client(host=ollama_host)

        risposta = client.chat(
            model=MODELLO_LLM,
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_utente}
            ],
            options={"temperature": 0.3, "num_ctx": 32000}
        )
        return risposta['message']['content'].strip()

    except Exception as e:
        print(f"[Errore Ollama]: {e}")
        return f"<p style='color: #dc3545;'>Errore durante la generazione del report intelligente: {e}</p>"