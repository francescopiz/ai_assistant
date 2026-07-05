import json
import os
import re
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict

import ollama
from services.database import get_preference
from services.llm_wiki import read_page, create_page, append_to_page, search_wiki, log_wiki_action, get_wiki_paths

router = APIRouter()

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    temperature: float = 0.4

# Helper function to check if Ollama is reachable
def is_ollama_online():
    ollama_host = get_preference("OLLAMA_HOST", "http://localhost:11434")
    try:
        client = ollama.Client(host=ollama_host)
        client.list()
        return True
    except Exception:
        return False

# --- BACKGROUND MEMORY CONSOLIDATOR ---

def run_memory_consolidation(chat_history: List[Dict[str, str]]):
    """
    Background Task che analizza la conversazione per estrarre informazioni e
    aggiornare la Wiki in maniera asincrona.
    """
    print("🧠 [Memory Consolidator] Avvio analisi conversazione in background...")
    
    # Prepara la cronologia in formato testuale
    cronologia_txt = ""
    for msg in chat_history:
        if msg["role"] in ["user", "assistant"]:
            cronologia_txt += f"{msg['role'].upper()}: {msg['content']}\n"
            
    prompt_sistema = """Analizza la conversazione tra l'utente (USER) e l'assistente (ASSISTANT).
Identifica se l'utente ha condiviso nuove informazioni personali (es. preferenze, cibi preferiti, orari, contatti, progetti attivi, note salute, interessi) da ricordare a lungo termine.
Rispondi ESCLUSIVAMENTE con un oggetto JSON valido. Non aggiungere markdown o spiegazioni extra, solo il JSON.
Il JSON deve avere la seguente struttura:
{
  "has_new_info": true,
  "extracted_notes": [
    {
      "page_name": "NomeDellaNota",
      "action": "create" o "append",
      "content": "Testo dettagliato in formato markdown"
    }
  ]
}
Se non ci sono informazioni rilevanti da memorizzare, rispondi con:
{
  "has_new_info": false,
  "extracted_notes": []
}
"""

    ollama_host = get_preference("OLLAMA_HOST", "http://localhost:11434")
    model_name = get_preference("OLLAMA_MODEL", "gemma4:26b")
    
    # Se Ollama non è online, simuliamo il consolidamento per test se l'utente dice parole chiave
    if not is_ollama_online():
        print("⚠️ [Memory Consolidator] Ollama non in linea. Avvio simulazione consolidamento di test...")
        # Cerca trigger di test per simulare il consolidamento
        if any("ricorda" in msg["content"].lower() or "diario" in msg["content"].lower() for msg in chat_history):
            # Crea o appende a una pagina fittizia
            today_str = datetime = "2026-07-05" # data fittizia del test
            create_page("TestConsolidamento", "### Nota Consolidata in Fallback\nQuesta nota è stata creata dal consolidatore in modalità offline.")
            log_wiki_action("consolidate", "Simulato consolidamento di test per [[TestConsolidamento]]")
        return
        
    try:
        client = ollama.Client(host=ollama_host)
        risposta = client.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Ecco la conversazione:\n{cronologia_txt}"}
            ],
            options={"temperature": 0.1}
        )
        
        response_text = risposta['message']['content'].strip()
        # Estrai eventuale JSON racchiuso in ```json ... ```
        json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
            
        data = json.loads(response_text)
        
        if data.get("has_new_info") and data.get("extracted_notes"):
            for note in data["extracted_notes"]:
                page_name = note["page_name"]
                content = note["content"]
                action = note["action"]
                
                # --- CHECK CONFLITTI (LINTING) ---
                existing_content = read_page(page_name)
                if not existing_content.startswith("Errore:"):
                    # La pagina esiste già, valutiamo il conflitto
                    prompt_conflitto = f"""Hai rilevato nuove informazioni per la pagina '{page_name}':
Nuove informazioni:
{content}

Contenuto esistente della pagina:
{existing_content}

Verifica se ci sono contraddizioni o aggiornamenti di stato. Integra storicamente le informazioni (ad esempio aggiungendo una nota datata) anziché cancellare o ignorare il passato. Ritorna il testo markdown completo e integrato da salvare.
Rispondi ESCLUSIVAMENTE con il testo finale del file markdown, senza tag ``` o commenti."""
                    
                    risposta_conflitto = client.chat(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": "Sei un redattore d'élite che risolve conflitti informativi storicizzando le variazioni."},
                            {"role": "user", "content": prompt_conflitto}
                        ],
                        options={"temperature": 0.2}
                    )
                    
                    integrated_text = risposta_conflitto['message']['content'].strip()
                    # Sovrascrive la pagina con il testo integrato
                    wiki_path, _, _ = get_wiki_paths()
                    filepath = wiki_path / f"{page_name}.md"
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(integrated_text)
                    log_wiki_action("lint_resolve", f"Risolto conflitto ed integrato contenuto in [[{page_name}]]")
                else:
                    # Crea la nuova pagina
                    if action == "create":
                        create_page(page_name, content)
                    else:
                        # Se l'azione era append ma il file non c'era, lo creiamo
                        create_page(page_name, content)
                        
    except Exception as e:
        print(f"❌ [Memory Consolidator] Errore nel consolidamento memoria: {e}")

# --- API CHAT ENDPOINT ---

@router.post("")
async def chat_stream(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Endpoint per la chat con supporto di streaming SSE.
    Una volta completata la generazione, innesca la consolidazione della memoria in background.
    """
    messages_dict = [{"role": m.role, "content": m.content} for m in request.messages]
    
    # Aggiungi BackgroundTask per analizzare la conversazione al termine
    background_tasks.add_task(run_memory_consolidation, messages_dict)
    
    ollama_host = get_preference("OLLAMA_HOST", "http://localhost:11434")
    model_name = get_preference("OLLAMA_MODEL", "gemma4:26b")
    
    # Gestione del fallback se Ollama è offline
    if not is_ollama_online():
        # Fallback offline generator
        async def mock_generator():
            yield "data: " + json.dumps({
                "message": {
                    "role": "assistant",
                    "content": "💭 <think>Ollama non è attivo. Eseguo simulazione locale per test.</think>Ciao Francesco! Al momento sono in **modalità offline** poiché il server Ollama non è raggiungibile su " + ollama_host + ".\n\n"
                               "Tuttavia, gli endpoint di FastAPI, il database di configurazione SQLite, l'APScheduler e tutti i tool CRUD del file system della Wiki sono attivi e pronti per i tuoi test!"
                }
            }) + "\n"
            yield "data: [DONE]\n"
            
        return StreamingResponse(mock_generator(), media_type="text/event-stream")
        
    try:
        from services.media_utility import parse_and_attach_media
        if messages_dict and messages_dict[-1]["role"] == "user":
            media_b64 = parse_and_attach_media(messages_dict[-1]["content"])
            if media_b64:
                messages_dict[-1]["images"] = media_b64
                # Switch to Qwen multimodal model for visual analysis
                model_name = "gwen3.6:27b"

        client = ollama.Client(host=ollama_host)
        
        async def response_generator():
            # Chiama Ollama in modalità streaming
            stream = client.chat(
                model=model_name,
                messages=messages_dict,
                stream=True,
                think=True,
                options={"temperature": request.temperature, "num_ctx": 32000}
            )
            for chunk in stream:
                yield f"data: {json.dumps(chunk)}\n"
            yield "data: [DONE]\n"
            
        return StreamingResponse(response_generator(), media_type="text/event-stream")
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore connessione Ollama: {e}"
        )
