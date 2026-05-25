import os
import io
import zipfile
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# --- DEFINIZIONE DEI PERCORSI ASSOLUTI ---
# __file__ è il percorso di questo script (es: /tuo_progetto/src/script.py)
BASE_DIR = Path(__file__).resolve().parent  # Cartella 'src'
PROJECT_DIR = BASE_DIR.parent  # Cartella radice del progetto

# I file di configurazione Google li teniamo nella radice del progetto
CREDENTIALS_PATH = PROJECT_DIR / 'credentials.json'
TOKEN_PATH = PROJECT_DIR / 'token.json'

# La cartella 'data' viene posizionata nella radice del progetto
DATA_DIR = PROJECT_DIR / 'data'


def ottieni_credenziali():
    creds = None
    # Verifica l'esistenza usando il percorso assoluto di token.json
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Verifica se credentials.json esiste prima di usarlo
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"❌ Impossibile trovare il file '{CREDENTIALS_PATH}'. Assicurati che sia nella radice del progetto.")

            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        # Salva il token nella radice del progetto
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    return creds


def cerca_file_zip(service, nome_file="Connessione Salute.zip"):
    query = f"name = '{nome_file}' and trashed = false"
    risultati = service.files().list(q=query, fields="files(id, name)").execute()
    files = risultati.get('files', [])
    if not files:
        print(f"❌ File '{nome_file}' non trovato su Google Drive.")
        return None
    return files[0]['id']


def salva_file_locale(service, file_id):
    """Scarica lo zip da Google Drive ed estrae il database nella cartella data/"""
    nome_output_db = "health_connect_export.db"

    # Crea la cartella 'data' se non esiste (parents=True la crea se manca anche la radice, exist_ok evita errori se c'è già)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Percorso finale del database (es: /tuo_progetto/data/health_connect_export.db)
    percorso_finale_db = DATA_DIR / nome_output_db

    print("⏳ Download del file zip in corso da Google Drive...")
    richiesta = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, richiesta)

    done = False
    while done is False:
        status, done = downloader.next_chunk()

    print("✅ Download completato. Estrazione in corso...")
    fh.seek(0)

    try:
        with zipfile.ZipFile(fh, 'r') as z:
            # Legge i byte del database dallo ZIP
            db_bytes = z.read("health_connect_export.db")

            # Scrive il file dentro la cartella data/
            with open(percorso_finale_db, "wb") as f_out:
                f_out.write(db_bytes)

        print(f"🎉 Successo! Il file è stato salvato correttamente.")
        print(f"📍 Percorso: {percorso_finale_db.resolve()}")

    except Exception as e:
        print(f"❌ Errore durante l'estrazione o il salvataggio del file: {e}")


def main():
    try:
        creds = ottieni_credenziali()
        service = build('drive', 'v3', credentials=creds)

        file_id = cerca_file_zip(service, "Connessione Salute.zip")
        if file_id:
            salva_file_locale(service, file_id)

    except HttpError as error:
        print(f"Errore API Google: {error}")
    except Exception as e:
        print(f"Errore: {e}")


if __name__ == '__main__':
    main()