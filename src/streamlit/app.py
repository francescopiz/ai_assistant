import streamlit as st
import ollama
import pprint
import os
import re
from tools import LISTA_TOOL_DISPONIBILI, MAPPA_FUNZIONI_TOOL
from datetime import datetime

st.set_page_config(page_title="Assistente di Francesco", page_icon="🤖", layout="wide")
st.title("Assistente di Francesco")

MODELLO_DEFAULT = os.environ.get("OLLAMA_MODEL", "gemma4:26b")
client = ollama.Client(host='http://localhost:11434')


def get_local_models():
    try:
        model_list = client.list()
        return [model['model'] for model in model_list['models']]
    except Exception:
        return []


modelli_disponibili = get_local_models()

if not modelli_disponibili:
    st.error("Non è stato possibile connettersi a Ollama. Verifica che l'applicazione sia avviata.")
    st.stop()

default_index = 0
if MODELLO_DEFAULT in modelli_disponibili:
    default_index = modelli_disponibili.index(MODELLO_DEFAULT)

with st.sidebar:
    st.header("Impostazioni Agente")
    modello_selezionato = st.selectbox("Scegli il modello AI:", modelli_disponibili, index=default_index)

    st.markdown("---")
    st.subheader("Parametri di Ragionamento")

    attiva_thinking = st.toggle(
        "Visualizza Ragionamento (Thinking)",
        value=True,
        help="Mostra o nasconde i passaggi logici interni del modello in un box dedicato."
    )

    temperatura = st.slider(
        "Temperatura", min_value=0.0, max_value=1.5, value=0.4, step=0.1,
        help="Consigliato un valore basso (0.3 - 0.5) per evitare che il modello ignori i dati forniti dai tool."
    )

    st.markdown("---")
    st.subheader("Opzioni di Debug")
    mostra_debug_grezzo = st.checkbox("Mostra dati estratti dai Tool", value=True)
    mostra_cronologia_completa = st.checkbox("Mostra array JSON messaggi", value=False)

    st.markdown("---")
    if st.button("Cancella Cronologia"):
        st.session_state.messaggi = []
        st.rerun()

if "messaggi" not in st.session_state or len(st.session_state.messaggi) == 0:
    st.session_state.messaggi = [
        {
            "role": "system",
            "content": (
                f"Sei un assistente AI aggiornato in tempo reale, personale e riservato. Nota bene: oggi è il {datetime.now().strftime('%d %B %Y')}.\n\n"
                "Hai a disposizione i seguenti comportamenti mandatori:\n"
                "1. Quando l'utente fa domande su eventi recenti esterni, usa SEMPRE il tool 'cerca_su_internet'.\n"
                "2. Quando l'utente ti chiede informazioni relative al suo diario, alle sue note personali o a concetti del suo LLM Wiki, agisci come un NAVIGATORE DETERMINISTICO. Non inventare informazioni. Usa prima il tool 'elenco_note' per capire quali file esistono. Poi, chiama il tool 'leggi_nota' per esaminare i file d'interesse per intero.\n"
                "3. Nelle note del diario troverai collegamenti ipertestuali interni nel formato [[NomeNota]]. Usali attivamente come indizi per capire quali altre note richiamare successivamente per completare l'analisi del grafo dei pensieri dell'utente."
            )
        }
    ]

for messaggio in st.session_state.messaggi:
    if messaggio["role"] in ["user", "assistant"] and messaggio.get("content"):
        with st.chat_message(messaggio["role"]):
            # Rimuoviamo i tag di thinking dai vecchi messaggi stampati a schermo se l'utente ha disattivato l'opzione
            testo_da_mostrare = messaggio["content"]
            if not attiva_thinking:
                testo_da_mostrare = re.sub(r'<think>.*?</think>', '', testo_da_mostrare, flags=re.DOTALL)
            st.markdown(testo_da_mostrare)

if input_utente := st.chat_input("Scrivi qualcosa..."):

    with st.chat_message("user"):
        st.markdown(input_utente)
    st.session_state.messaggi.append({"role": "user", "content": input_utente})

    with st.chat_message("assistant"):
        # Contenitori dinamici per gestire la separazione visiva
        placeholder_thinking = st.empty()
        placeholder_risposta = st.empty()

        try:
            opzioni_modello = {
                "temperature": temperatura,
                "num_ctx": 32000
            }

            # Prima passata per i Tool con parametro think legato alla scelta utente
            risposta = client.chat(
                model=modello_selezionato,
                messages=st.session_state.messaggi,
                tools=LISTA_TOOL_DISPONIBILI,
                think=attiva_thinking,
                options=opzioni_modello
            )

            while 'tool_calls' in risposta['message'] and risposta['message']['tool_calls']:
                st.session_state.messaggi.append(risposta['message'])

                for tool_call in risposta['message']['tool_calls']:
                    nome_funzione = tool_call['function']['name']
                    argomenti = tool_call['function']['arguments']

                    st.toast(f"🛠️ Il modello ha attivato il Tool: `{nome_funzione}`", icon="🔍")

                    with st.status(f"Ispezione Esecuzione: {nome_funzione}", expanded=True) as status:
                        if 'query' in argomenti:
                            st.write(f"**Query generata dall'AI:** `{argomenti.get('query', '')}`")
                        elif 'nome_file' in argomenti:
                            st.write(f"**File richiesto dall'AI:** `{argomenti.get('nome_file', '')}`")
                        else:
                            st.write(f"**Esecuzione tool ad ampio spettro**")

                        if nome_funzione in MAPPA_FUNZIONI_TOOL:
                            funzione_reale = MAPPA_FUNZIONI_TOOL[nome_funzione]
                            risultato_funzione = funzione_reale(**argomenti)

                            if mostra_debug_grezzo:
                                st.markdown(f"**Risultati grezzi restituiti dal Tool (`{nome_funzione}`):**")
                                st.code(risultato_funzione, language="text")

                            status.update(label=f"Tool `{nome_funzione}` eseguito correttamente!", state="complete")
                        else:
                            risultato_funzione = f"Errore: Il tool {nome_funzione} non esiste."
                            status.update(label="Errore esecuzione tool", state="error")

                        st.session_state.messaggi.append({
                            'role': 'tool',
                            'name': nome_funzione,
                            'content': str(risultato_funzione)
                        })

                risposta = client.chat(
                    model=modello_selezionato,
                    messages=st.session_state.messaggi,
                    tools=LISTA_TOOL_DISPONIBILI,
                    think=attiva_thinking,
                    options=opzioni_modello
                )

            if mostra_cronologia_completa:
                with st.expander("Ispezione Struttura Messaggi (JSON)", expanded=True):
                    st.json(st.session_state.messaggi)

            print("\n--- CRONOLOGIA INVIATA A OLLAMA ---")
            pprint.pprint(st.session_state.messaggi)
            print("----------------------------------\n")

            # STREAMING FINALE CON SEPARAZIONE DEL THINKING
            risposta_completa = ""
            testo_thinking = ""
            in_thinking_block = False

            stream_finale = client.chat(
                model=modello_selezionato,
                messages=st.session_state.messaggi,
                stream=True,
                think=True,  # Chiediamo sempre il thinking a Ollama per salvarlo in cronologia...
                options=opzioni_modello
            )

            for chunk in stream_finale:
                if 'message' in chunk:
                    msg = chunk['message']

                    # Gestione campo esplicito 'thinking' (se supportato dall'SDK/modello)
                    if 'thinking' in msg and msg['thinking']:
                        testo_thinking += msg['thinking']
                        if attiva_thinking:
                            with placeholder_thinking.expander("💭 Ragionamento dell'Agente...", expanded=True):
                                st.write(testo_thinking)
                        continue

                    # Gestione tag classici <think> all'interno di 'content'
                    if 'content' in msg:
                        content_chunk = msg['content']
                        risposta_completa += content_chunk

                        # Controllo apertura/chiusura tag di thinking nel testo grezzo
                        if "<think>" in content_chunk:
                            in_thinking_block = True
                        if "</think>" in content_chunk:
                            in_thinking_block = False

                        # Estrazione del testo dentro <think> per scopi grafici
                        match_thinking = re.search(r'<think>(.*?)(</think>|$)', risposta_completa, re.DOTALL)
                        if match_thinking:
                            testo_thinking = match_thinking.group(1).strip()
                            if attiva_thinking and testo_thinking:
                                with placeholder_thinking.expander("💭 Ragionamento dell'Agente...", expanded=True):
                                    st.write(testo_thinking)

                        # Isola la risposta pulita dai tag <think> da mostrare all'utente
                        risposta_pulita = re.sub(r'<think>.*?</think>', '', risposta_completa, flags=re.DOTALL)
                        if in_thinking_block:
                            risposta_pulita = re.sub(r'<think>.*', '', risposta_completa, flags=re.DOTALL)

                        # Mostra la risposta finale solo se non siamo nel pieno del blocco di thinking (o se l'utente vuole comunque vedere lo stream)
                        if risposta_pulita.strip() or not attiva_thinking:
                            placeholder_risposta.markdown(risposta_pulita + "▌")

            # Pulizia finale dei placeholder senza il cursore di digitazione
            risposta_pulita_finale = re.sub(r'<think>.*?</think>', '', risposta_completa, flags=re.DOTALL).strip()

            if attiva_thinking and testo_thinking:
                with placeholder_thinking.expander("💭 Ragionamento dell'Agente...", expanded=False):
                    st.write(testo_thinking)
            else:
                placeholder_thinking.empty()  # Rimuove il box se l'utente non lo voleva

            placeholder_risposta.markdown(risposta_pulita_finale)

            # Salviamo l'intera risposta (incluso il thinking, se presente) nella cronologia per il contesto futuro dell'LLM
            st.session_state.messaggi.append({"role": "assistant", "content": risposta_completa})

        except Exception as e:
            st.error(f"Si è verificato un errore durante la generazione: {e}")