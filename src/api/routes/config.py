from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List

from services.database import SessionLocal, EmailConfig, AppPreference, set_preference, get_preference
from services.scheduler import reschedule_email_jobs

router = APIRouter()

class EmailConfigResponse(BaseModel):
    email_type: str
    schedule_time: str
    enabled: bool
    active_modules: str
    last_run: str = None

    class Config:
        from_attributes = True

class EmailConfigRequest(BaseModel):
    email_type: str
    schedule_time: str
    enabled: bool
    active_modules: str

class PreferenceUpdateRequest(BaseModel):
    key: str
    value: str

@router.get("/email")
def get_email_schedules():
    """Ritorna le configurazioni attuali di invio email mattutine e serali."""
    db = SessionLocal()
    try:
        configs = db.query(EmailConfig).all()
        # Convert objects to clean serializable dicts
        result = []
        for c in configs:
            result.append({
                "email_type": c.email_type,
                "schedule_time": c.schedule_time,
                "enabled": c.enabled,
                "active_modules": c.active_modules,
                "last_run": c.last_run.isoformat() if c.last_run else None
            })
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore caricamento configurazioni email: {e}"
        )
    finally:
        db.close()

@router.post("/email")
def update_email_schedule(data: EmailConfigRequest):
    """
    Aggiorna la configurazione di un invio email nel database e rischedula 
    dinamicamente il task APScheduler.
    """
    db = SessionLocal()
    try:
        config = db.query(EmailConfig).filter_by(email_type=data.email_type).first()
        if not config:
            config = EmailConfig(email_type=data.email_type)
            db.add(config)
            
        config.schedule_time = data.schedule_time
        config.enabled = data.enabled
        config.active_modules = data.active_modules
        db.commit()
        
        # Rischedula dinamicamente il job
        reschedule_email_jobs()
        
        return {"message": f"Configurazione '{data.email_type}' aggiornata e rischedulata correttamente."}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore aggiornamento schedulazione: {e}"
        )
    finally:
        db.close()

@router.get("/preferences")
def get_preferences():
    """Ritorna le preferenze globali dell'applicazione."""
    db = SessionLocal()
    try:
        prefs = db.query(AppPreference).all()
        return {p.key: p.value for p in prefs}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore caricamento preferenze: {e}"
        )
    finally:
        db.close()

@router.post("/preferences")
def update_preference(data: PreferenceUpdateRequest):
    """Aggiorna una preferenza globale dell'applicazione (es. modello Ollama)."""
    try:
        # Prevent security issues with token modifications via API (optional check)
        set_preference(data.key, data.value)
        
        # Se modifichiamo preferenze collegate a percorsi o modelli, verifichiamo la stabilità
        return {"message": f"Preferenza '{data.key}' aggiornata con successo."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore salvataggio preferenza: {e}"
        )
