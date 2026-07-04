import os
from llama_index.llms.ollama import Ollama
from llama_index.core.tools import FunctionTool

MODELLO_LLM = os.environ.get("OLLAMA_MODEL", "gemma4:26b")
# 1. IMPORT AGGIORNATO (Nuovo sistema Workflow di LlamaIndex)
from llama_index.core.agent.workflow import ReActAgent

# Costanti e definizioni dei tool (rimangono uguali)
PATH_TO_WIKI = r"C:\Users\pizzu\Desktop\ai_assistant\data\wiki"  # Usa il tuo percorso reale


def elenco_note() -> list:
    """Restituisce l'elenco di tutte le note presenti nel diario/wiki."""
    if not os.path.exists(PATH_TO_WIKI):
        return ["Errore: Percorso Wiki non trovato."]
    return [f for f in os.listdir(PATH_TO_WIKI) if f.endswith(".md")]


def leggi_nota(nome_file: str) -> str:
    """Legge l'intero contenuto di una nota specifica."""
    if not nome_file.endswith(".md"):
        nome_file += ".md"
    filepath = os.path.join(PATH_TO_WIKI, nome_file)
    if not os.path.exists(filepath):
        return f"Errore: La nota '{nome_file}' non esiste."
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


tool_elenco = FunctionTool.from_defaults(fn=elenco_note)
tool_leggi = FunctionTool.from_defaults(fn=leggi_nota)

# 2. CONFIGURAZIONE LLM
llm = Ollama(model=MODELLO_LLM, request_timeout=300.0, base_url="http://localhost:11434")

# 3. CREAZIONE AGENTE (Inizializzazione diretta nel costruttore)
agent = ReActAgent(
    name="WikiNavigator",
    description="Un agente che naviga direttamente i file markdown del diario.",
    tools=[tool_elenco, tool_leggi],
    llm=llm,
    system_prompt="""Sei un assistente personale che naviga direttamente il diario dell'utente strutturato come una Wiki.
    Devi esplorare le note leggendole per intero.
    Nelle note troverai link ad altre note scritti come [[NomeNota]]. Usa questi link per capire dove cercare.
    Inizia sempre guardando l'elenco delle note, poi apri i file necessari uno alla volta per rispondere alla domanda."""
)

# 4. ESECUZIONE (I nuovi agenti basati su workflow usano .run() anziché .chat())
domanda = "Controlla le mie note e scrivi un piccolo report (massimo 5 frasi) che riassumono chi è l'autore e che tipo di persona è. Sii oggettivo e obiettivo."

print("Lancio dell'agente sulla Wiki...")
# Nota: .run() è sincrono/asincrono a seconda del contesto, LlamaIndex workflow supporta il run diretto
import asyncio


async def main():
    response = await agent.run(user_msg=domanda)
    print("\n🤖 RISPOSTA FINALE:")
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
