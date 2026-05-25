import json
from ddgs import DDGS

def cerca_su_internet(query: str) -> str:
    """
    Effettua una ricerca sul web usando DuckDuckGo per raccogliere informazioni aggiornate.
    """
    try:
        with DDGS() as ddgs:
            # Recuperiamo i risultati reali dal web
            risultati = list(ddgs.text(query, max_results=10))
            if not risultati:
                return "Nessun risultato trovato su DuckDuckGo per questa ricerca."
            
            output = []
            for res in risultati:
                output.append(f"Titolo: {res.get('title')}\nURL: {res.get('href')}\nContenuto: {res.get('body')}\n---")
            return "\n".join(output)
    except Exception as ex:
        return f"Errore durante la ricerca web locale: {ex}"

tool_ricerca_web = {
    'type': 'function',
    'function': {
        'name': 'cerca_su_internet',
        'description': 'Usa questo tool OBBLIGATORIAMENTE quando l\'utente chiede notizie recenti, risultati sportivi, fatti del 2025/2026, meteo o qualsiasi informazione che richieda dati aggiornati in tempo reale.',
        'parameters': {
            'type': 'object',
            'properties': {
                'query': {
                    'type': 'string',
                    'description': 'La stringa di ricerca ottimizzata per i motori di ricerca (es. "vincitore serie a 2026", "classifica campionato italiano 2025 2026")',
                },
            },
            'required': ['query'],
        },
    },
}

LISTA_TOOL_DISPONIBILI = [tool_ricerca_web]

MAPPA_FUNZIONI_TOOL = {
    'cerca_su_internet': cerca_su_internet
}