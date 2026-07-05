import streamlit as st
import requests
import json
import re
import os
from datetime import datetime

# Setup page layout
st.set_page_config(page_title="Secondo Cervello OS Dashboard", page_icon="🧠", layout="wide")
st.title("🧠 Secondo Cervello OS & Personal Wiki")

# Load configuration / Bearer token from local environment or default
DEFAULT_TOKEN = os.environ.get("API_BEARER_TOKEN", "secure_secret_token_12345")
API_URL = os.environ.get("API_URL", "http://localhost:8000")

# Session state initialization
if "bearer_token" not in st.session_state:
    st.session_state.bearer_token = DEFAULT_TOKEN

with st.sidebar:
    st.header("🔑 Connessione Core")
    api_url = st.text_input("FastAPI Base URL:", value=API_URL, key="api_url_input")
    token = st.text_input("Bearer Token:", value=st.session_state.bearer_token, type="password")
    st.session_state.bearer_token = token
    
    st.markdown("---")
    st.subheader("Stato del Sistema")
    
    # Check if API is online
    headers = {"Authorization": f"Bearer {token}"}
    try:
        res = requests.get(f"{api_url}/", headers=headers, timeout=2)
        if res.status_code == 200:
            st.success("🟢 API Core: ONLINE")
        elif res.status_code == 401:
            st.error("🔴 API Core: NON AUTORIZZATO (Token errato)")
        else:
            st.warning(f"🟡 API Core: Codice {res.status_code}")
    except Exception:
        st.error("🔴 API Core: OFFLINE (Connessione fallita)")

    if st.button("Pulisci Cronologia Chat"):
        st.session_state.chat_history = []
        st.toast("Cronologia chat locale azzerata.")

# Tabs configuration
tab_chat, tab_wiki, tab_ingest, tab_config = st.tabs([
    "💬 Chat Intelligente", 
    "📂 Wiki Navigator & Editor", 
    "📥 Ingest Audio & Diario", 
    "⚙️ Email & Impostazioni"
])

# Helpers for API calls
def api_get(endpoint):
    headers = {"Authorization": f"Bearer {st.session_state.bearer_token}"}
    try:
        r = requests.get(f"{api_url}{endpoint}", headers=headers)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 401:
            st.error("Errore di autenticazione: token non valido.")
        else:
            st.error(f"Errore API {r.status_code}: {r.text}")
    except Exception as e:
        st.error(f"Errore connessione: {e}")
    return None

def api_post(endpoint, json_data):
    headers = {"Authorization": f"Bearer {st.session_state.bearer_token}"}
    try:
        r = requests.post(f"{api_url}{endpoint}", json=json_data, headers=headers)
        if r.status_code == 200:
            return r.json()
        else:
            st.error(f"Errore API {r.status_code}: {r.text}")
    except Exception as e:
        st.error(f"Errore connessione: {e}")
    return None

def api_put(endpoint, json_data):
    headers = {"Authorization": f"Bearer {st.session_state.bearer_token}"}
    try:
        r = requests.put(f"{api_url}{endpoint}", json=json_data, headers=headers)
        if r.status_code == 200:
            return r.json()
        else:
            st.error(f"Errore API {r.status_code}: {r.text}")
    except Exception as e:
        st.error(f"Errore connessione: {e}")
    return None

# ==========================================
# 1. TAB CHAT
# ==========================================
with tab_chat:
    st.header("Conversazione con il Secondo Cervello")
    st.caption("Al termine di ogni chat, la memoria in background (Consolidator) scansiona la conversazione per aggiornare la Wiki.")
    
    # Load settings from preferences if possible
    prefs = api_get("/api/config/preferences") or {}
    model_name = prefs.get("OLLAMA_MODEL", "gemma4:26b")
    
    col1, col2 = st.columns([4, 1])
    with col2:
        temp = st.slider("Temperatura:", min_value=0.0, max_value=1.5, value=0.4, step=0.1)
        attiva_thinking = st.toggle("Mostra Ragionamento (Thinking)", value=True)
        st.info(f"Modello attivo: `{model_name}`")

    # Initializing chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {"role": "assistant", "content": "Ciao! Sono il gestore del tuo Secondo Cervello. Puoi chiedermi informazioni sulle tue note, sul tuo diario o chiedermi di memorizzare qualcosa."}
        ]

    # Show messages
    for msg in st.session_state.chat_history:
        with col1.chat_message(msg["role"]):
            content = msg["content"]
            if not attiva_thinking:
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
            st.markdown(content)

    if prompt_utente := col1.chat_input("Chiedi qualcosa al tuo Secondo Cervello..."):
        with col1.chat_message("user"):
            st.markdown(prompt_utente)
        st.session_state.chat_history.append({"role": "user", "content": prompt_utente})
        
        with col1.chat_message("assistant"):
            placeholder_thinking = st.empty()
            placeholder_content = st.empty()
            
            # Request SSE stream from API
            headers = {"Authorization": f"Bearer {st.session_state.bearer_token}"}
            messages_payload = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_history]
            
            try:
                response = requests.post(
                    f"{api_url}/api/chat",
                    json={"messages": messages_payload, "temperature": temp},
                    headers=headers,
                    stream=True
                )
                
                full_response = ""
                thinking_text = ""
                in_thinking = False
                
                if response.status_code == 200:
                    for line in response.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith("data: "):
                                data_str = decoded_line[6:]
                                if data_str.strip() == "[DONE]":
                                    break
                                
                                try:
                                    chunk = json.loads(data_str)
                                    msg_chunk = chunk.get("message", {})
                                    
                                    # Handle chunk thinking
                                    if "thinking" in msg_chunk and msg_chunk["thinking"]:
                                        thinking_text += msg_chunk["thinking"]
                                        if attiva_thinking:
                                            with placeholder_thinking.expander("💭 Ragionamento dell'Agente...", expanded=True):
                                                st.write(thinking_text)
                                        continue
                                        
                                    if "content" in msg_chunk and msg_chunk["content"]:
                                        content_chunk = msg_chunk["content"]
                                        full_response += content_chunk
                                        
                                        # Detect classical <think> tags in content
                                        if "<think>" in content_chunk:
                                            in_thinking = True
                                        if "</think>" in content_chunk:
                                            in_thinking = False
                                            
                                        match_think = re.search(r'<think>(.*?)(</think>|$)', full_response, re.DOTALL)
                                        if match_think and match_think.group(1).strip():
                                            thinking_text = match_think.group(1).strip()
                                            if attiva_thinking:
                                                with placeholder_thinking.expander("💭 Ragionamento dell'Agente...", expanded=True):
                                                    st.write(thinking_text)
                                                    
                                        # Clean response from thinking tags
                                        clean_resp = re.sub(r'<think>.*?</think>', '', full_response, flags=re.DOTALL)
                                        if in_thinking:
                                            clean_resp = re.sub(r'<think>.*', '', full_response, flags=re.DOTALL)
                                            
                                        if clean_resp.strip() or not attiva_thinking:
                                            placeholder_content.markdown(clean_resp + "▌")
                                except Exception:
                                    pass
                    
                    # Clean final layout
                    clean_final = re.sub(r'<think>.*?</think>', '', full_response, flags=re.DOTALL).strip()
                    placeholder_content.markdown(clean_final)
                    if attiva_thinking and thinking_text:
                        with placeholder_thinking.expander("💭 Ragionamento dell'Agente...", expanded=False):
                            st.write(thinking_text)
                    else:
                        placeholder_thinking.empty()
                        
                    st.session_state.chat_history.append({"role": "assistant", "content": full_response})
                    st.toast("🧠 Memory Consolidator avviato in background!")
                else:
                    st.error(f"Errore chat ({response.status_code}): {response.text}")
            except Exception as ex:
                st.error(f"Connessione fallita: {ex}")

# ==========================================
# 2. TAB WIKI
# ==========================================
with tab_wiki:
    st.header("Navigatore e Editor delle Note (LLM Wiki)")
    
    col_w1, col_w2 = st.columns([1, 2])
    
    with col_w1:
        st.subheader("Note Disponibili")
        q_search = st.text_input("Cerca nel Wiki (Query):", key="wiki_search")
        
        pages_res = api_get(f"/api/wiki/pages?query={q_search}" if q_search else "/api/wiki/pages")
        available_pages = pages_res.get("pages", []) if pages_res else []
        
        selected_page = st.radio("Seleziona una pagina:", available_pages) if available_pages else None
        
        st.markdown("---")
        st.subheader("🆕 Nuova Nota")
        new_title = st.text_input("Titolo Nota (PascalCase o YYYY-MM-DD):")
        new_content = st.text_area("Contenuto Markdown iniziale:", height=150)
        if st.button("Crea Pagina"):
            if new_title and new_content:
                res = api_post("/api/wiki/pages", {"page_name": new_title, "content": new_content})
                if res:
                    st.success(res.get("message", "Creata!"))
                    st.rerun()
            else:
                st.warning("Compila titolo e contenuto!")
                
    with col_w2:
        if selected_page:
            st.subheader(f"Dettaglio Nota: `{selected_page}`")
            page_data = api_get(f"/api/wiki/pages/{selected_page}")
            
            if page_data:
                content = page_data.get("content", "")
                
                # Mode: View or Edit
                mode = st.radio("Modalità:", ["Visualizzazione", "Modifica"], horizontal=True, key=f"mode_{selected_page}")
                
                if mode == "Visualizzazione":
                    # Render bidirection links nicely
                    # Make [[Link]] look highlighted
                    rendered_markdown = re.sub(r'\[\[(.*?)\]\]', r'**`[[\1]]`**', content)
                    st.markdown(rendered_markdown)
                else:
                    edited_content = st.text_area("Modifica Markdown:", value=content, height=450, key=f"edit_area_{selected_page}")
                    
                    col_b1, col_b2 = st.columns(2)
                    if col_b1.button("Salva Sovrascrivendo"):
                        res = api_put(f"/api/wiki/pages/{selected_page}", {"action": "overwrite", "content": edited_content})
                        if res:
                            st.success("Modifiche salvate con successo.")
                            st.rerun()
                    if col_b2.button("Appendi in coda"):
                        to_append = st.text_input("Testo da appendere in coda:")
                        if to_append:
                            res = api_put(f"/api/wiki/pages/{selected_page}", {"action": "append", "content": to_append})
                            if res:
                                st.success("Testo appeso con successo.")
                                st.rerun()
        else:
            st.info("Nessuna nota selezionata. Selezionane una a sinistra per vederne il contenuto.")

# ==========================================
# 3. TAB INGEST
# ==========================================
with tab_ingest:
    st.header("Caricamento Fonti e Diario Vocale")
    
    col_i1, col_i2 = st.columns(2)
    
    with col_i1:
        st.subheader("🎙️ Upload Nota Vocale (Audio)")
        st.caption("Carica file audio. Verrà trascritto da Whisper in background e processato dall'Ingest Agent.")
        audio_file = st.file_uploader("Scegli file audio (mp3, wav, m4a):", type=["mp3", "wav", "m4a"])
        
        # Test simulate option
        is_mock_upload = st.checkbox("Nota Audio di Test (Simula Whisper)", value=True, help="Se attivo, la trascrizione sarà simulata velocemente per i test offline.")
        
        if st.button("Carica ed Ingest"):
            if audio_file:
                # Prepare filename for upload
                fname = audio_file.name
                if is_mock_upload and not fname.lower().startswith("mock"):
                    fname = f"mock_{fname}"
                    
                files = {"file": (fname, audio_file.read(), audio_file.type)}
                headers = {"Authorization": f"Bearer {st.session_state.bearer_token}"}
                
                try:
                    with st.spinner("Invio file al server in corso..."):
                        r = requests.post(f"{api_url}/api/audio/upload", files=files, headers=headers)
                        if r.status_code == 200:
                            st.success(r.json().get("message", "Caricamento completato!"))
                        else:
                            st.error(f"Errore: {r.status_code} - {r.text}")
                except Exception as ex:
                    st.error(f"Connessione fallita: {ex}")
            else:
                st.warning("Seleziona prima un file!")
                
        st.markdown("---")
        st.subheader("✍️ Diario Diretto (Text Entry)")
        st.caption("Scrivi direttamente del testo. Verrà aggiunto al diario di oggi ed elaborato in background.")
        diary_text = st.text_area("Cosa vuoi scrivere sul diario oggi?", height=150)
        if st.button("Invia Nota Scritta"):
            if diary_text:
                res = api_post("/api/audio/add-journal-entry", {"text": diary_text})
                if res:
                    st.success(res.get("message", "Inviato!"))
                    st.rerun()
            else:
                st.warning("Digita del testo!")

    with col_i2:
        st.subheader("📜 Registro Attività LLM (log.md)")
        st.caption("Visualizza le operazioni svolte dagli agenti in background (ingest, linting, consolidate).")
        
        log_data = api_get("/api/wiki/pages/log")
        if log_data:
            st.text_area("log.md:", value=log_data.get("content", ""), height=400, disabled=True)
        else:
            st.info("Log non ancora disponibile o vuoto.")

# ==========================================
# 4. TAB CONFIGURATION
# ==========================================
with tab_config:
    st.header("Configurazione Schedulazione Email & Preferenze")
    
    col_c1, col_c2 = st.columns(2)
    
    with col_c1:
        st.subheader("📅 Email Schedulate")
        
        email_configs = api_get("/api/config/email")
        if email_configs:
            for config in email_configs:
                e_type = config["email_type"]
                st.markdown(f"#### Email di tipo: **{e_type.upper()}**")
                
                enabled = st.checkbox(f"Abilita invio {e_type}", value=config["enabled"], key=f"en_{e_type}")
                schedule_time = st.text_input(f"Orario di invio ({e_type}):", value=config["schedule_time"], key=f"time_{e_type}")
                
                # Active modules selection
                all_modules = ["health", "weather", "news", "on_this_day", "goals", "action_items", "wiki_lint"]
                current_modules = [m.strip() for m in config["active_modules"].split(",") if m.strip()]
                
                st.write("Moduli attivi per questa mail:")
                selected_modules = []
                for mod in all_modules:
                    if st.checkbox(f"Modulo: {mod}", value=(mod in current_modules), key=f"mod_{e_type}_{mod}"):
                        selected_modules.append(mod)
                        
                if st.button(f"Aggiorna Schedulazione {e_type.upper()}"):
                    payload = {
                        "email_type": e_type,
                        "schedule_time": schedule_time,
                        "enabled": enabled,
                        "active_modules": ",".join(selected_modules)
                    }
                    res = api_post("/api/config/email", payload)
                    if res:
                        st.success(f"Orario e moduli per {e_type} aggiornati!")
                        st.rerun()
                st.markdown("---")
        else:
            st.warning("Configurazioni email non trovate.")
            
    with col_c2:
        st.subheader("⚙️ Preferenze Applicazione")
        
        prefs = api_get("/api/config/preferences")
        if prefs:
            model = st.text_input("Ollama Model:", value=prefs.get("OLLAMA_MODEL", "gemma4:26b"))
            host = st.text_input("Ollama Host:", value=prefs.get("OLLAMA_HOST", "http://localhost:11434"))
            w_path = st.text_input("Wiki Folder Path:", value=prefs.get("WIKI_PATH", ""))
            raw_p = st.text_input("Raw Sources Path:", value=prefs.get("RAW_SOURCES_PATH", ""))
            
            # API Token update
            curr_token = st.text_input("API Key (Bearer Token):", value=prefs.get("BEARER_TOKEN", ""), type="password")
            
            if st.button("Salva Preferenze Globali"):
                # Save each preference
                api_post("/api/config/preferences", {"key": "OLLAMA_MODEL", "value": model})
                api_post("/api/config/preferences", {"key": "OLLAMA_HOST", "value": host})
                api_post("/api/config/preferences", {"key": "WIKI_PATH", "value": w_path})
                api_post("/api/config/preferences", {"key": "RAW_SOURCES_PATH", "value": raw_p})
                api_post("/api/config/preferences", {"key": "BEARER_TOKEN", "value": curr_token})
                
                st.session_state.bearer_token = curr_token
                st.success("Preferenze aggiornate nel database.")
                st.rerun()
        else:
            st.warning("Preferenze globali non caricate.")