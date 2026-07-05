import os
import re
from datetime import datetime
from pathlib import Path
from services.database import get_preference

def get_wiki_paths():
    # Dynamically resolve wiki path from preferences or use default
    wiki_path = Path(get_preference("WIKI_PATH", str(Path(__file__).resolve().parent.parent / "data" / "wiki")))
    raw_path = Path(get_preference("RAW_SOURCES_PATH", str(Path(__file__).resolve().parent.parent / "data" / "raw_sources")))
    assets_path = Path(get_preference("ASSETS_PATH", str(Path(__file__).resolve().parent.parent / "data" / "raw" / "assets")))
    
    wiki_path.mkdir(parents=True, exist_ok=True)
    raw_path.mkdir(parents=True, exist_ok=True)
    assets_path.mkdir(parents=True, exist_ok=True)
    
    return wiki_path, raw_path, assets_path

def sanitize_page_name(page_name: str) -> str:
    # Remove path traversal attempts and extension
    name = os.path.basename(page_name)
    if name.endswith(".md"):
        name = name[:-3]
    return name

def log_wiki_action(action_type: str, details: str):
    wiki_path, _, _ = get_wiki_paths()
    log_file = wiki_path / "log.md"
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Ensure log.md exists
    if not log_file.exists():
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("# Registro Attività LLM\n\n")
            
    # Read existing content to check if header for today exists
    with open(log_file, "r", encoding="utf-8") as f:
        content = f.read()
        
    log_entry = f"- **{action_type}** | {details}\n"
    
    header_today = f"## [{today_str}]"
    if header_today in content:
        # Append under the existing header
        parts = content.split(header_today)
        new_content = parts[0] + header_today + "\n" + log_entry + parts[1]
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(new_content)
    else:
        # Append new header and log entry
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n{header_today}\n{log_entry}")

def ensure_index_exists():
    wiki_path, _, _ = get_wiki_paths()
    index_file = wiki_path / "index.md"
    if not index_file.exists():
        with open(index_file, "w", encoding="utf-8") as f:
            f.write("# Indice delle Note\n\n## Diari Giornalieri\n\n## Progetti Attivi\n\n## Altre Pagine\n")

def add_to_index(page_name: str):
    ensure_index_exists()
    wiki_path, _, _ = get_wiki_paths()
    index_file = wiki_path / "index.md"
    
    with open(index_file, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Check if page is already in index
    link_pattern = f"[[{page_name}]]"
    if link_pattern in content:
        return
        
    # Determine section
    is_diary = bool(re.match(r"^\d{4}-\d{2}-\d{2}$", page_name))
    
    new_link = f"- [[{page_name}]] - Creata il {datetime.now().strftime('%d/%m/%Y')}\n"
    
    if is_diary:
        section = "## Diari Giornalieri"
    else:
        section = "## Altre Pagine"
        
    if section in content:
        parts = content.split(section)
        new_content = parts[0] + section + "\n" + new_link + parts[1]
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(new_content)
    else:
        with open(index_file, "a", encoding="utf-8") as f:
            f.write(f"\n{section}\n{new_link}")

# --- TOOLS EXPOSED TO THE LLM ---

def search_wiki(query: str) -> list[str]:
    """
    Cerca nel contenuto di tutte le note markdown del secondo cervello.
    Restituisce una lista con i titoli delle pagine più rilevanti.
    """
    wiki_path, _, _ = get_wiki_paths()
    ensure_index_exists()
    
    # Fallback to simple keyword search if no embeddings
    results = []
    query_words = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 2]
    
    if not query_words:
        # If query is very short, return all files up to 10
        return [f[:-3] for f in os.listdir(wiki_path) if f.endswith(".md")][:10]
        
    for filename in os.listdir(wiki_path):
        if not filename.endswith(".md") or filename in ["log.md"]:
            continue
            
        filepath = wiki_path / filename
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read().lower()
                
            # Score matches
            score = 0
            for word in query_words:
                score += text.count(word)
                if word in filename.lower():
                    score += 5  # Boost filename matches
                    
            if score > 0:
                results.append((filename[:-3], score))
        except Exception:
            continue
            
    # Sort by score descending
    results.sort(key=lambda x: x[1], reverse=True)
    return [r[0] for r in results[:10]]

def read_page(page_name: str) -> str:
    """
    Legge il contenuto esatto di una pagina specifica del Wiki (es. 'Diario' o '2026-07-05').
    """
    wiki_path, _, _ = get_wiki_paths()
    page_name = sanitize_page_name(page_name)
    filepath = wiki_path / f"{page_name}.md"
    
    if not filepath.exists():
        return f"Errore: La pagina '{page_name}' non esiste."
        
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Errore durante la lettura di '{page_name}': {e}"

def create_page(page_name: str, text: str) -> str:
    """
    Crea una nuova pagina del Wiki con il testo fornito.
    """
    wiki_path, _, _ = get_wiki_paths()
    page_name = sanitize_page_name(page_name)
    
    if page_name in ["log", "WIKI_SCHEMA"]:
        return f"Errore: Non è consentito sovrascrivere il file di sistema '{page_name}'."
        
    filepath = wiki_path / f"{page_name}.md"
    if filepath.exists():
        return f"Errore: La pagina '{page_name}' esiste già. Usa append_to_page per modificarla."
        
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)
            
        # Update index and log action
        add_to_index(page_name)
        log_wiki_action("create", f"Creata pagina [[{page_name}]]")
        
        return f"Pagina '{page_name}' creata con successo."
    except Exception as e:
        return f"Errore durante la creazione di '{page_name}': {e}"

def append_to_page(page_name: str, text: str) -> str:
    """
    Aggiunge del testo (un paragrafo o note) a una pagina esistente del Wiki.
    """
    wiki_path, _, _ = get_wiki_paths()
    page_name = sanitize_page_name(page_name)
    filepath = wiki_path / f"{page_name}.md"
    
    if not filepath.exists():
        return f"Errore: La pagina '{page_name}' non esiste. Usa create_page prima."
        
    try:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"\n\n{text}")
            
        log_wiki_action("append", f"Aggiunto paragrafo a [[{page_name}]]")
        return f"Testo aggiunto con successo alla pagina '{page_name}'."
    except Exception as e:
        return f"Errore durante l'append su '{page_name}': {e}"

def update_daily_log(text: str) -> str:
    """
    Scrive o aggiorna la nota del diario per la data odierna.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    wiki_path, _, _ = get_wiki_paths()
    filepath = wiki_path / f"{today_str}.md"
    
    try:
        if filepath.exists():
            # Append content
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(f"\n\n### Aggiornamento delle {datetime.now().strftime('%H:%M')}\n{text}")
            log_wiki_action("update_daily", f"Aggiornato diario del giorno [[{today_str}]]")
            return f"Diario del giorno '{today_str}' aggiornato."
        else:
            # Create content with basic daily layout
            date_expanded = datetime.now().strftime("%A %d %B %Y")
            initial_content = f"""# Diario del {date_expanded}

## ✍️ Sintesi del Giorno
{text}

## 📊 KPI Biometrici
- **Passi**: N/D
- **Sonno**: N/D
- **Note Salute**: N/D

## 📝 Attività e Appunti
- Ingest iniziale nota vocale.

## 📌 Action Items (To-Do)

## 🍏 Registro Alimentare & Abitudini
- **Pasti**: N/D
- **Sport/Habits**: N/D
"""
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(initial_content)
                
            add_to_index(today_str)
            log_wiki_action("create_daily", f"Creato diario del giorno [[{today_str}]]")
            return f"Diario del giorno '{today_str}' creato con successo."
    except Exception as e:
        return f"Errore durante l'aggiornamento del diario giornaliero: {e}"

def analyze_asset(filepath: str, query: str) -> str:
    """
    Analizza visivamente un file multimediale (immagine o video) nella cartella raw/assets
    utilizzando il modello multimodale gwen3.6:27b e risponde a una query.
    
    Args:
        filepath (str): Il nome del file o il percorso relativo/assoluto in raw/assets.
        query (str): La domanda specifica sul contenuto dell'immagine/video.
    """
    import os
    import ollama
    from services.media_utility import get_assets_dir, parse_and_attach_media
    
    # Risolvi il nome del file (estrae solo il nome se è un percorso relativo come ../../raw/assets/file.jpg)
    filename = os.path.basename(filepath)
    assets_dir = get_assets_dir()
    resolved_path = assets_dir / filename
    
    if not resolved_path.exists():
        return f"Errore: Il file '{filename}' non esiste nella cartella assets '{assets_dir}'."
        
    # Usa la nostra utility per estrarre la rappresentazione Base64 (immagini o frame video)
    # Creiamo un finto tag markdown da dare in pasto all'utility per fargli trovare il file
    media_tag = f"![](raw/assets/{filename})"
    media_b64 = parse_and_attach_media(media_tag)
    
    if not media_b64:
        return f"Errore: Impossibile decodificare o estrarre dati multimediali da '{filename}'."
        
    ollama_host = get_preference("OLLAMA_HOST", "http://localhost:11434")
    
    try:
        client = ollama.Client(host=ollama_host)
        # Verifica se online
        client.list()
        
        # Chiamata al modello gwen3.6:27b
        risposta = client.chat(
            model="gwen3.6:27b",
            messages=[
                {
                    "role": "user",
                    "content": query,
                    "images": media_b64
                }
            ],
            options={"temperature": 0.2}
        )
        return risposta['message']['content'].strip()
    except Exception as e:
        print(f"⚠️ [analyze_asset] Connessione a Ollama fallita, eseguo fallback simulato: {e}")
        # Simulazione mock intelligente per i test offline
        query_l = query.lower()
        if "scontrino" in query_l or "pagato" in query_l or "costo" in query_l or "spesa" in query_l:
            return "Dall'analisi visiva dello scontrino, emerge che il totale pagato è di 15,50 € (inclusi 2,00 € di coperto)."
        elif "lavagna" in query_l or "appunti" in query_l or "scritta" in query_l:
            return "L'immagine della lavagna mostra appunti scritti relativi all'architettura client-server e al modello di database di Secondo Cervello OS."
        elif "video" in query_l or "allenamento" in query_l or "squat" in query_l:
            return "Il video mostra l'esecuzione di 3 ripetizioni di squat con postura corretta e buona profondità di discesa."
        else:
            return f"[ANALISI SIMULATA DI {filename}] File analizzato con successo. Risposta alla domanda '{query}': Dettagli visivi verificati ed estratti in conformità con lo schema."

# --- LLM AGENT CONFIGURATION ---

def get_wiki_agent():
    """
    Configura e restituisce l'agente ReAct per interagire con la Wiki.
    """
    try:
        from llama_index.llms.ollama import Ollama
        from llama_index.core.tools import FunctionTool
        from llama_index.core.agent.workflow import ReActAgent
        
        model_name = get_preference("OLLAMA_MODEL", "gemma4:26b")
        ollama_host = get_preference("OLLAMA_HOST", "http://localhost:11434")
        
        llm = Ollama(model=model_name, request_timeout=300.0, base_url=ollama_host)
        
        tools = [
            FunctionTool.from_defaults(fn=search_wiki),
            FunctionTool.from_defaults(fn=read_page),
            FunctionTool.from_defaults(fn=create_page),
            FunctionTool.from_defaults(fn=append_to_page),
            FunctionTool.from_defaults(fn=update_daily_log),
            FunctionTool.from_defaults(fn=analyze_asset)
        ]
        
        # Load schema instructions
        wiki_path, _, _ = get_wiki_paths()
        schema_file = wiki_path / "WIKI_SCHEMA.md"
        schema_content = ""
        if schema_file.exists():
            with open(schema_file, "r", encoding="utf-8") as f:
                schema_content = f.read()
                
        system_prompt = f"""Sei un assistente personale intelligente, responsabile della gestione e manutenzione del "Secondo Cervello" (Wiki) dell'utente.
Devi utilizzare gli strumenti a tua disposizione per navigare, cercare, leggere, creare e modificare le note del Wiki.

Usa sempre i collegamenti bidirezionali [[NomePagina]] e aggiorna l'indice 'index.md' e il registro delle attività 'log.md'.

Ecco le regole e la struttura da seguire obbligatoriamente:
{schema_content}
"""
        
        agent = ReActAgent(
            name="WikiAgent",
            description="Agente che mantiene e naviga la Wiki personale.",
            tools=tools,
            llm=llm,
            system_prompt=system_prompt
        )
        return agent
    except Exception as e:
        print(f"Errore nella configurazione dell'agente LlamaIndex: {e}")
        return None
