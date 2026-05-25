import os
import ollama

# 1. Impostiamo il modello corretto che hai effettivamente sul PC
MODELLO_LLM = os.environ.get("OLLAMA_MODEL", "gemma4:26b")


def genera_report_html(notizie_grezze: str) -> str:
    """Interroga Ollama per sintetizzare le notizie direttamente in formato HTML."""
    if not notizie_grezze or "FONTE:" not in notizie_grezze:
        return "<p style='color: #777777;'>Nessuna notizia rilevante estratta per oggi.</p>"

    prompt_sistema = (
        "Sei un caporedattore esperto. Il tuo compito è prendere una lista di notizie del mattino "
        "e creare un report di sintesi focalizzato esclusivamente sulle notizie più importanti del giorno.\n\n"
        "REGOLE DI FORMATTAZIONE STRICHE:\n"
        "1. Rispondi USANDO ESCLUSIVAMENTE TAG HTML validi inseriti nel testo corpo (es: <h3>, <p>, <ul>, <li>, <strong>, <a>).\n"
        "2. NON racchiudere la risposta in blocchi di codice markdown come ```html ... ```. Scrivi direttamente il testo HTML.\n"
        "3. Usa uno stile grafico pulito (es: per i link usa un colore blu come style='color: #206bc4; text-decoration: none;').\n"
        "4. Dividi il report in massimo 3 macro-categorie (es: Attualità Globale, Tecnologia e Scienza, Economia)."
    )

    prompt_utente = f"Ecco le notizie grezze raccolte:\n\n{notizie_grezze}"

    try:
        ollama_host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        if "0.0.0.0" in ollama_host:
            ollama_host = ollama_host.replace("0.0.0.0", "127.0.0.1")
        
        if not ollama_host.startswith("http"):
            ollama_host = "http://" + ollama_host
            
        client = ollama.Client(host=ollama_host)

        print(f"Chiamata a Ollama con il modello: {MODELLO_LLM}...")
        risposta = client.chat(
            model=MODELLO_LLM,
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_utente}
            ],
            options={
                "temperature": 0.3,
                "num_ctx": 32000
            }
        )
        return risposta['message']['content'].strip()

    except Exception as e:
        print(f"[Errore Ollama]: Impossibile generare il report. Dettaglio: {e}")
        return f"<p style='color: #dc3545;'>Errore durante la generazione del report notizie: {e}</p>"