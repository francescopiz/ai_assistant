import streamlit as st
import ollama
import pprint
from tools import LISTA_TOOL_DISPONIBILI, MAPPA_FUNZIONI_TOOL
from datetime import datetime

st.set_page_config(page_title="Assistente di Francesco", page_icon="🤖", layout="wide")
st.title("Assistente di Francesco")

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


with st.sidebar:
    st.header("Impostazioni Agente")
    modello_selezionato = st.selectbox("Scegli il modello AI:", modelli_disponibili, index=0)
    
    st.markdown("---")
    st.subheader("Parametri di Ragionamento")
    
    attiva_thinking = st.toggle(
        "Attiva Ragionamento (Thinking)", 
        value=True,
        help="Mostra o nasconde i passaggi logici interni del modello."
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
                f"Sei un assistente AI aggiornato in tempo reale. Nota bene: oggi è il {datetime.now().strftime('%d %B %Y')}. "
                "Quando l'utente fa domande su events recenti, usa SEMPRE il tool 'cerca_su_internet' e rispondi "
                "basandoti sui dati testuali restituiti dallo strumento."
            )
        }
    ]

for messaggio in st.session_state.messaggi:
    if messaggio["role"] in ["user", "assistant"] and messaggio.get("content"):
        with st.chat_message(messaggio["role"]):
            st.markdown(messaggio["content"])


if input_utente := st.chat_input("Scrivi qualcosa..."):
    
    with st.chat_message("user"):
        st.markdown(input_utente)
    st.session_state.messaggi.append({"role": "user", "content": input_utente})
    
    with st.chat_message("assistant"):
        placeholder_risposta = st.empty()
        
        try:
            opzioni_modello = {
                "temperature": temperatura,
                "num_ctx": 32000
            }
            
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
                    
                    st.toast(f"🛠️ Modello ha attivato il Tool: `{nome_funzione}`", icon="🔍")
                    
                    with st.status(f"Ispezione Esecuzione: {nome_funzione}", expanded=True) as status:
                        st.write(f"**Query generata dall'AI:** `{argomenti.get('query', '')}`")
                        
                        if nome_funzione in MAPPA_FUNZIONI_TOOL:
                            funzione_reale = MAPPA_FUNZIONI_TOOL[nome_funzione]
                            risultato_funzione = funzione_reale(**argomenti)
                            
                            if mostra_debug_grezzo:
                                st.markdown("**Risultati grezzi restituiti da DuckDuckGo:**")
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

            risposta_completa = ""
            stream_finale = client.chat(
                model=modello_selezionato,
                messages=st.session_state.messaggi,
                stream=True,
                think=attiva_thinking,
                options=opzioni_modello
            )
            
            for chunk in stream_finale:
                if 'message' in chunk and 'content' in chunk['message']:
                    risposta_completa += chunk['message']['content']
                    placeholder_risposta.markdown(risposta_completa + "▌")
                
            placeholder_risposta.markdown(risposta_completa)
            st.session_state.messaggi.append({"role": "assistant", "content": risposta_completa})
            
        except Exception as e:
            st.error(f"Si è verificato un errore durante la generazione: {e}")