import os
from ddgs import DDGS

# Costanti e configurazioni del percorso Wiki
PATH_TO_WIKI = r"C:\Users\pizzu\Desktop\ai_assistant\data\wiki"


def cerca_su_internet(query: str) -> str:
    """
    Effettua una ricerca sul web usando DuckDuckGo per raccogliere informazioni aggiornate.
    """
    try:
        with DDGS() as ddgs:
            risultati = list(ddgs.text(query, max_results=10))
            if not risultati:
                return "Nessun risultato trovato su DuckDuckGo per questa ricerca."

            output = []
            for res in risultati:
                output.append(f"Titolo: {res.get('title')}\nURL: {res.get('href')}\nContenuto: {res.get('body')}\n---")
            return "\n".join(output)
    except Exception as ex:
        return f"Errore durante la ricerca web locale: {ex}"


def elenco_note() -> str:
    """
    Restituisce l'elenco di tutte le note presenti nel diario/wiki locale.
    """
    if not os.path.exists(PATH_TO_WIKI):
        return "Errore: Percorso LLM-Wiki non trovato sul sistema locale."
    file_list = [f for f in os.listdir(PATH_TO_WIKI) if f.endswith(".md")]
    if not file_list:
        return "Il tuo LLM-Wiki è vuoto o non contiene file .md."
    return "File disponibili nel Wiki:\n" + "\n".join(file_list)


def leggi_nota(nome_file: str) -> str:
    """
    Legge l'intero contenuto di una nota specifica dal tuo Wiki/diario locale.
    """
    if not nome_file.endswith(".md"):
        nome_file += ".md"
    filepath = os.path.join(PATH_TO_WIKI, nome_file)
    if not os.path.exists(filepath):
        return f"Errore: La nota '{nome_file}' non esiste nel Wiki."
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Errore durante la lettura del file: {e}"


# --- SCHEMI DEFINIZIONE TOOL PER OLLAMA ---

tool_ricerca_web = {
    'type': 'function',
    'function': {
        'name': 'cerca_su_internet',
        'description': "Usa questo tool OBBLIGATORIAMENTE quando l'utente chiede notizie recenti, fatti del 2025/2026, meteo o informazioni esterne in tempo reale.",
        'parameters': {
            'type': 'object',
            'properties': {
                'query': {
                    'type': 'string',
                    'description': 'La stringa di ricerca ottimizzata per i motori di ricerca.',
                },
            },
            'required': ['query'],
        },
    },
}

tool_elenco_wiki = {
    'type': 'function',
    'function': {
        'name': 'elenco_note',
        'description': "Usa questo tool come primo passaggio quando l'utente fa domande sul suo diario personale, pensieri o sul suo LLM Wiki, per vedere quali file sono disponibili.",
        'parameters': {
            'type': 'object',
            'properties': {},
        },
    },
}

tool_leggi_wiki = {
    'type': 'function',
    'function': {
        'name': 'leggi_nota',
        'description': "Usa questo tool per leggere interamente una nota specifica del diario (es. 'Ansia.md' o '2026-07-01.md'). All'interno troverai collegamenti ad altre note scritti come [[NomeNota]] che potrai navigare successivamente.",
        'parameters': {
            'type': 'object',
            'properties': {
                'nome_file': {
                    'type': 'string',
                    'description': "Il nome esatto del file comprensivo o meno di estensione .md (es: 'Stress.md' o 'Note-Lavoro')",
                },
            },
            'required': ['nome_file'],
        },
    },
}

# Esportazione cumulativa per Streamlit
LISTA_TOOL_DISPONIBILI = [tool_ricerca_web, tool_elenco_wiki, tool_leggi_wiki]

MAPPA_FUNZIONI_TOOL = {
    'cerca_su_internet': cerca_su_internet,
    'elenco_note': elenco_note,
    'leggi_nota': leggi_nota
}