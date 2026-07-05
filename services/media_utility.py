import os
import re
import base64
from pathlib import Path
from services.database import get_preference

def get_assets_dir() -> Path:
    # Resolve assets directory from preferences or use default
    default_path = Path(__file__).resolve().parent.parent / "data" / "raw" / "assets"
    assets_path = Path(get_preference("ASSETS_PATH", str(default_path)))
    assets_path.mkdir(parents=True, exist_ok=True)
    return assets_path

def parse_and_attach_media(text: str) -> list[str]:
    """
    Scansiona il testo per cercare riferimenti a file multimediali nella cartella raw/assets.
    Converte le immagini (.jpg, .png) in Base64 e i video (.mp4) in un array di 5 frame Base64.
    Ritorna la lista di tutte le stringhe Base64 estratte.
    """
    if not text:
        return []
        
    assets_dir = get_assets_dir()
    base64_assets = []
    
    # Regex per trovare file con estensioni immagini/video preceduti da segmenti del tipo raw/assets/ o assets/
    # Es: ![ricevuta](../../raw/assets/scontrino_123.jpg) -> scontrino_123.jpg
    media_pattern = r'(?:raw/assets/|assets/|assets\\)([A-Za-z0-9_\-\.\%\s]+\.(?:jpg|jpeg|png|mp4))'
    matches = list(set(re.findall(media_pattern, text, re.IGNORECASE)))
    
    for filename in matches:
        # Pulisce eventuali spazi o caratteri percentuali url-encoded
        filename_clean = filename.replace("%20", " ").strip()
        filepath = assets_dir / filename_clean
        
        if not filepath.exists():
            print(f"⚠️ [Media Middleware] File referenziato non trovato in assets: {filepath}")
            continue
            
        ext = filepath.suffix.lower()
        
        # --- CASO IMMAGINI ---
        if ext in [".jpg", ".jpeg", ".png"]:
            try:
                with open(filepath, "rb") as f:
                    b64_str = base64.b64encode(f.read()).decode("utf-8")
                    base64_assets.append(b64_str)
                print(f"🖼️ [Media Middleware] Immagine allegata con successo: {filename_clean}")
            except Exception as e:
                print(f"❌ [Media Middleware] Errore codifica Base64 per immagine {filename_clean}: {e}")
                
        # --- CASO VIDEO (.mp4) ---
        elif ext == ".mp4":
            try:
                # Carichiamo cv2 pigramente
                import cv2
                
                cap = cv2.VideoCapture(str(filepath))
                if not cap.isOpened():
                    print(f"❌ [Media Middleware] Impossibile aprire il video {filename_clean} con OpenCV")
                    continue
                    
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if total_frames <= 0:
                    print(f"❌ [Media Middleware] Video {filename_clean} non ha frame validi")
                    cap.release()
                    continue
                    
                # Estraiamo 5 frame equidistanti lungo il video
                num_frames = 5
                frame_indices = [int(i * total_frames / num_frames) for i in range(num_frames)]
                
                extracted_count = 0
                for idx in frame_indices:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                    success, frame = cap.read()
                    if not success:
                        continue
                        
                    # Ridimensiona il frame a max 640x480 per non intasare la memoria del payload Ollama
                    h, w = frame.shape[:2]
                    if w > 640 or h > 480:
                        scale = min(640/w, 480/h)
                        frame = cv2.resize(frame, (int(w*scale), int(h*scale)))
                        
                    # Codifica in JPG
                    success, buffer = cv2.imencode(".jpg", frame)
                    if success:
                        b64_str = base64.b64encode(buffer).decode("utf-8")
                        base64_assets.append(b64_str)
                        extracted_count += 1
                        
                cap.release()
                print(f"🎥 [Media Middleware] Video '{filename_clean}' processato. Estratti {extracted_count} frame.")
            except ImportError:
                print("⚠️ [Media Middleware] Libreria 'opencv-python' non disponibile. Impossibile estrarre frame video.")
            except Exception as e:
                print(f"❌ [Media Middleware] Errore estrazione frame da {filename_clean}: {e}")
                
    return base64_assets
