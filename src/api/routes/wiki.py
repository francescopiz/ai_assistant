import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Body, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from services.llm_wiki import (
    search_wiki, read_page, create_page, append_to_page, 
    get_wiki_paths, sanitize_page_name
)

router = APIRouter()

class CreatePageRequest(BaseModel):
    page_name: str
    content: str

class UpdatePageRequest(BaseModel):
    action: str = "append"  # 'append' or 'overwrite'
    content: str

@router.get("/pages")
def list_pages(query: str = None):
    """
    Ritorna la lista di tutte le note presenti nel secondo cervello.
    Se è passata una query, esegue una ricerca semantica/keyword.
    """
    wiki_path, _, _ = get_wiki_paths()
    if query:
        return {"pages": search_wiki(query)}
        
    try:
        pages = [f[:-3] for f in os.listdir(wiki_path) if f.endswith(".md")]
        return {"pages": pages}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore recupero pagine: {e}"
        )

@router.get("/pages/{page_name}")
def get_page(page_name: str):
    """Legge il contenuto di una nota specifica."""
    content = read_page(page_name)
    if content.startswith("Errore:"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=content
        )
    return {
        "page_name": sanitize_page_name(page_name),
        "content": content
    }

@router.post("/pages")
def create_new_page(data: CreatePageRequest):
    """Crea una nuova nota nel Secondo Cervello."""
    res = create_page(data.page_name, data.content)
    if res.startswith("Errore:"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res
        )
    return {"message": res}

@router.put("/pages/{page_name}")
def update_existing_page(page_name: str, data: UpdatePageRequest):
    """Modifica o appende contenuto a una nota esistente."""
    page_name = sanitize_page_name(page_name)
    wiki_path, _, _ = get_wiki_paths()
    filepath = wiki_path / f"{page_name}.md"
    
    if data.action == "append":
        res = append_to_page(page_name, data.content)
        if res.startswith("Errore:"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=res
            )
        return {"message": res}
        
    elif data.action == "overwrite":
        # Consenti la sovrascrittura diretta
        if not filepath.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"La pagina '{page_name}' non esiste."
            )
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(data.content)
            from services.llm_wiki import log_wiki_action
            log_wiki_action("overwrite", f"Sovrascritta pagina [[{page_name}]]")
            return {"message": f"Pagina '{page_name}' sovrascritta correttamente."}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Errore sovrascrittura file: {e}"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Azione non valida. Deve essere 'append' o 'overwrite'."
        )

@router.post("/upload-asset")
async def upload_asset(file: UploadFile = File(...)):
    """Salva immagini o file multimediali per referenziarli nelle note del Wiki."""
    _, _, assets_path = get_wiki_paths()
    
    filename = os.path.basename(file.filename)
    dest_path = assets_path / filename
    
    try:
        content = await file.read()
        with open(dest_path, "wb") as f:
            f.write(content)
            
        # Ritorna il path relativo servibile per l'embedding markdown
        asset_url = f"/api/wiki/assets/{filename}"
        return {
            "message": f"File '{filename}' caricato correttamente.",
            "url": asset_url,
            "filename": filename
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore caricamento asset: {e}"
        )

@router.get("/assets/{filename}")
def serve_asset(filename: str):
    """Endpoint per servire gli asset del Wiki."""
    _, _, assets_path = get_wiki_paths()
    file_path = assets_path / filename
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset non trovato."
        )
    return FileResponse(path=str(file_path))
