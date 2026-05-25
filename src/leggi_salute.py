import os
import io
import zipfile
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def ottieni_credenziali():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('../token.json', 'w') as token:
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

import sqlite3

def salva_file_locale(service, file_id):
    """Scarica lo zip da Google Drive ed estrae il database sul computer locale"""
    nome_output_db = "health_connect_export.db"
    
    print("⏳ Download del file zip in corso da Google Drive...")
    richiesta = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, richiesta)
    
    done = False
    while done is False:
        status, done = downloader.next_chunk()
            
    print("✅ Download completato. Estrazione in corso...")
    fh.seek(0)
    
    # Apriamo lo ZIP memorizzato nei byte ed estraiamo il file sul computer
    try:
        with zipfile.ZipFile(fh, 'r') as z:
            # Legge i byte del database dallo ZIP
            db_bytes = z.read("health_connect_export.db")
            
            # Crea e scrive il file nella cartella corrente del tuo computer
            with open(nome_output_db, "wb") as f_out:
                f_out.write(db_bytes)
                
        print(f"🎉 Successo! Il file è stato salvato correttamente sul tuo PC.")
        print(f"📍 Percorso: {os.path.abspath(nome_output_db)}")
        
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