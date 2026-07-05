import os
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Integer, Text
from sqlalchemy.orm import declarative_base, sessionmaker

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CURRENT_DIR.parent if CURRENT_DIR.name in ["src", "services"] else CURRENT_DIR
DB_DIR = PROJECT_DIR / "data"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "app.db"

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class AppPreference(Base):
    __tablename__ = "app_preferences"
    
    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=False)

class EmailConfig(Base):
    __tablename__ = "email_configs"
    
    email_type = Column(String, primary_key=True, index=True)  # 'morning' or 'evening'
    schedule_time = Column(String, nullable=False, default="07:00")  # 'HH:MM'
    enabled = Column(Boolean, nullable=False, default=True)
    active_modules = Column(String, nullable=False, default="health,weather,news,on_this_day,goals,action_items,wiki_lint")
    last_run = Column(DateTime, nullable=True)

class ScheduledTaskLog(Base):
    __tablename__ = "scheduled_task_logs"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task_name = Column(String, nullable=False)
    run_time = Column(DateTime, default=datetime.utcnow)
    status = Column(String, nullable=False)  # 'SUCCESS' or 'FAILED'
    details = Column(Text, nullable=True)

def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Pre-populate default values if they don't exist
    session = SessionLocal()
    try:
        # Defaults for email configs
        morning = session.query(EmailConfig).filter_by(email_type="morning").first()
        if not morning:
            session.add(EmailConfig(
                email_type="morning",
                schedule_time="07:00",
                enabled=True,
                active_modules="health,weather,news,on_this_day,goals,action_items,wiki_lint"
            ))
            
        evening = session.query(EmailConfig).filter_by(email_type="evening").first()
        if not evening:
            session.add(EmailConfig(
                email_type="evening",
                schedule_time="19:00",
                enabled=False,
                active_modules="health,action_items,wiki_lint"
            ))
            
        # Defaults for preferences
        defaults = {
            "OLLAMA_MODEL": os.environ.get("OLLAMA_MODEL", "gemma4:26b"),
            "OLLAMA_HOST": os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            "WIKI_PATH": str(PROJECT_DIR / "data" / "wiki"),
            "RAW_SOURCES_PATH": str(PROJECT_DIR / "data" / "raw_sources"),
            "ASSETS_PATH": str(PROJECT_DIR / "data" / "raw" / "assets"),
            "BEARER_TOKEN": os.environ.get("API_BEARER_TOKEN", "secure_secret_token_12345")
        }
        
        for key, val in defaults.items():
            pref = session.query(AppPreference).filter_by(key=key).first()
            if not pref:
                session.add(AppPreference(key=key, value=val))
                
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error seeding database: {e}")
    finally:
        session.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_preference(key: str, default: str = None) -> str:
    session = SessionLocal()
    try:
        pref = session.query(AppPreference).filter_by(key=key).first()
        return pref.value if pref else default
    finally:
        session.close()

def set_preference(key: str, value: str):
    session = SessionLocal()
    try:
        pref = session.query(AppPreference).filter_by(key=key).first()
        if pref:
            pref.value = value
        else:
            session.add(AppPreference(key=key, value=value))
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
