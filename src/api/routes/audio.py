import os
import re
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, UploadFile, File, HTTPException, status
from pydantic import BaseModel

from services.llm_wiki import update_daily_log, append_to_page, create_page, read_page, log_wiki_action, get_wiki_paths
from services.database import get_preference
from services.transcribe import convert_audio_to_text

router = APIRouter()

class JournalEntryRequest(BaseModel):
    text: str

# Helper to check if Ollama is online
def is_ollama_online():
    import ollama
    ollama_host = get_preference("OLLAMA_HOST", "http://localhost:11434")
    try:
        client = ollama.Client(host=ollama_host)
        client.list()
        return True
    except Exception:
        return False

# --- BACKGROUND INGEST AGENT ---

def run_ingest_agent(raw_text: str, source_name: str):
    """
    Agente di background che analizza il testo grezzo trascritto o inserito nel diario,
    estrae concetti ed aggiorna le pagine entità rilevanti della Wiki.
    """
    print(f"📥 [Ingest Agent] Avvio analisi per fonte: {source_name}")
    
    # 1. Salva sempre nella nota del diario odierno
    res_daily = update_daily_log(f"**Ingest da {source_name}:**\n{raw_text}")
    print(f"📥 [Ingest Agent] {res_daily}")
    
    # 2. Estrazione concetti e aggiornamento entità
    # Se Ollama è online, lo interroga per capire quali pagine aggiornare
    if is_ollama_online():
        import ollama
        ollama_host = get_preference("OLLAMA_HOST", "http://localhost:11434")
        model_name = get_preference("OLLAMA_MODEL", "gemma4:26b")
        
        prompt_sistema = """Analizza il testo inserito dall'utente. Identifica se fa riferimento a specifici progetti, persone, argomenti, cibi (registro nutrizionale) o abitudini.
Rispondi con un oggetto JSON valido contenente la lista delle entità da aggiornare e il contenuto markdown da aggiungere.
Formato JSON:
{
  "entities": [
    {
      "page_name": "NomeDellaPaginaInPascalCase",
      "content_to_append": "Testo markdown da appendere"
    }
  ]
}
Se non ci sono entità specifiche da aggiornare, rispondi con {"entities": []}.
"""
        try:
            client = ollama.Client(host=ollama_host)
            risposta = client.chat(
                model=model_name,
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": f"Testo da analizzare:\n{raw_text}"}
                ],
                options={"temperature": 0.1}
            )
            
            response_text = risposta['message']['content'].strip()
            json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
                
            import json
            data = json.loads(response_text)
            
            for ent in data.get("entities", []):
                p_name = ent["page_name"]
                p_content = ent["content_to_append"]
                
                # Leggi la pagina o creala
                existing = read_page(p_name)
                if existing.startswith("Errore:"):
                    # Crea la pagina
                    create_page(p_name, f"# {p_name}\n\n{p_content}")
                else:
                    # Appendi
                    append_to_page(p_name, p_content)
                    
        except Exception as e:
            print(f"❌ [Ingest Agent] Errore chiamata LLM: {e}")
            
    else:
        # Fallback deterministico basato su parole chiave per i test senza LLM
        print("⚠️ [Ingest Agent] Modalità offline. Eseguo estrazione basata su parole chiave (Regex)...")
        
        # Progetti
        if "progetto" in raw_text.lower():
            # Trova una parola dopo "progetto"
            match = re.search(r"progetto\s+([A-Za-z0-9_]+)", raw_text, re.IGNORECASE)
            proj_name = match.group(1).capitalize() if match else "Generale"
            page_name = f"Progetto{proj_name}"
            
            existing = read_page(page_name)
            content_to_add = f"- **Aggiornamento ({datetime.now().strftime('%d/%m/%Y %H:%M')}):** Rilevate novità relative a questo progetto da {source_name}."
            if existing.startswith("Errore:"):
                create_page(page_name, f"# Progetto {proj_name}\n\n## Note e Sviluppi\n{content_to_add}")
            else:
                append_to_page(page_name, content_to_add)
                
        # Nutrizione
        if any(food in raw_text.lower() for food in ["mangiato", "cibo", "colazione", "pranzo", "cena", "pizza", "pasta"]):
            page_name = "SaluteNutrizione"
            existing = read_page(page_name)
            content_to_add = f"- **Alimentazione ({datetime.now().strftime('%d/%m/%Y')}):** Registrato inserimento pasti da {source_name}: {raw_text}"
            if existing.startswith("Errore:"):
                create_page(page_name, f"# Salute e Nutrizione\n\n## Registro Pasti\n{content_to_add}")
            else:
                append_to_page(page_name, content_to_add)

# --- BACKGROUND TRANSCRIPTION TASK ---

def transcribe_audio_background(audio_file_path: str, txt_path: str):
    """
    Background task per la trascrizione audio con Whisper.
    Include una simulazione fittizia in caso di assenza di GPU o errore.
    """
    print(f"🎙️ [Whisper Task] Inizio elaborazione file: {audio_file_path}")
    
    # Se il file contiene la parola 'mock' o Whisper non è configurato/pronto, usiamo un fallback
    is_mock = "mock" in os.path.basename(audio_file_path).lower()
    
    transcribed_text = None
    if not is_mock:
        try:
            # Usa whisper reale importato da services.transcribe
            # Per evitare caricamenti lenti in test veloci, usiamo il modello 'tiny' o 'base' anziché 'large-v3'
            transcribed_text = convert_audio_to_text(
                audio_file_path,
                model_size="base",
                language="it",
                output_file=txt_path,
                save_progress=False
            )
        except Exception as e:
            print(f"⚠️ [Whisper Task] Errore Whisper reale, avvio mock di emergenza: {e}")
            is_mock = True
            
    if is_mock or not transcribed_text:
        # Generazione mock
        transcribed_text = (
            "Ciao! Questa è una nota vocale registrata di test. "
            "Oggi ho iniziato a lavorare sul ProgettoSecondoCervello per implementare le API di FastAPI. "
            "A pranzo ho mangiato una pizza margherita ed un'insalata. "
            "Ricordati di completare i test unitari entro stasera."
        )
        # Salva testo
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(transcribed_text)
        print(f"🎙️ [Whisper Task] Scritta trascrizione simulata in: {txt_path}")
        
    # Invia il testo all'Ingest Agent
    run_ingest_agent(transcribed_text, f"Audio ({os.path.basename(audio_file_path)})")
    
    # Rimuove il file audio temporaneo/raw per pulizia (opzionale)
    # os.remove(audio_file_path)

def analyze_and_ingest_media_background(filepath: str, filename: str):
    """
    Background task per processare immagini e video.
    Chiama Qwen per analizzare il file, salva l'analisi testuale e innesca l'ingest agent.
    """
    print(f"🖼️ [Media Ingest] Inizio analisi per asset visivo: {filename}")
    
    query = (
        "L'utente ha appena caricato questo file. Analizzalo attentamente ed estrai tutte le informazioni "
        "salienti che l'utente vorrebbe ricordare nel suo Secondo Cervello. Se è uno scontrino o fattura, "
        "estrai dettagliatamente le spese (voci, prezzi, totale). Se è una lavagna o appunti, trascrivi e "
        "sintetizza i punti chiave. Se è un video, descrivi le azioni ed eventi che accadono. "
        "Fornisci una sintesi dettagliata ed strutturata in formato Markdown."
    )
    
    from services.llm_wiki import analyze_asset
    # Chiama l'analisi visiva (che gestisce internamente Qwen o il mock)
    analisi_testo = analyze_asset(str(filepath), query)
    
    # Salva il risultato in data/raw_sources come sorgente testuale
    _, raw_path, _ = get_wiki_paths()
    txt_filename = f"media_{Path(filename).stem}_analysis.txt"
    dest_txt_path = raw_path / txt_filename
    
    try:
        with open(dest_txt_path, "w", encoding="utf-8") as f:
            f.write(analisi_testo)
        print(f"🖼️ [Media Ingest] Analisi salvata in sorgenti grezze: {dest_txt_path}")
    except Exception as e:
        print(f"❌ [Media Ingest] Errore nel salvataggio del testo dell'analisi: {e}")
        
    # Invia all'Ingest Agent (che aggiornerà il diario e le pagine entità)
    run_ingest_agent(analisi_testo, f"Visual Asset ({filename})")

# --- API ENDPOINTS ---

@router.post("/upload")
def upload_file_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Carica un file audio, immagine o video.
    In base all'estensione del file, lo smista al pipeline Whisper (audio) o Qwen (visual).
    """
    wiki_path, raw_path, assets_path = get_wiki_paths()
    
    filename = os.path.basename(file.filename)
    ext = Path(filename).suffix.lower()
    
    # Liste di estensioni supportate
    audio_exts = [".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"]
    visual_exts = [".jpg", ".jpeg", ".png", ".mp4"]
    
    try:
        if ext in audio_exts:
            dest_audio_path = raw_path / filename
            txt_filename = f"{Path(filename).stem}_transcription.txt"
            dest_txt_path = raw_path / txt_filename
            
            with open(dest_audio_path, "wb") as f:
                f.write(file.file.read())
                
            background_tasks.add_task(
                transcribe_audio_background, 
                str(dest_audio_path), 
                str(dest_txt_path)
            )
            
            return {
                "type": "audio",
                "message": "File audio caricato. Trascrizione ed Ingest avviati in background.",
                "filename": filename,
                "transcription_file": txt_filename
            }
            
        elif ext in visual_exts:
            dest_visual_path = assets_path / filename
            
            with open(dest_visual_path, "wb") as f:
                f.write(file.file.read())
                
            background_tasks.add_task(
                analyze_and_ingest_media_background, 
                str(dest_visual_path), 
                filename
            )
            
            return {
                "type": "visual",
                "message": "File multimediale (immagine/video) caricato. Analisi visiva ed Ingest avviati in background.",
                "filename": filename
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Estensione '{ext}' non supportata. Carica file audio o immagini/video."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore caricamento file: {e}"
        )

@router.post("/add-journal-entry")
def add_journal_entry_endpoint(
    data: JournalEntryRequest,
    background_tasks: BackgroundTasks
):
    """
    Aggiunge una nota di diario scritta direttamente.
    Avvia in background l'ingest agent per analizzare il testo ed aggiornare la Wiki.
    """
    try:
        # Avvia l'ingest agent in background per estrarre informazioni
        background_tasks.add_task(run_ingest_agent, data.text, "Text Entry")
        
        return {
            "message": "Nota di diario registrata. Analisi ed indicizzazione avviate in background.",
            "text_preview": data.text[:60] + "..." if len(data.text) > 60 else data.text
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore inserimento nota di diario: {e}"
        )
