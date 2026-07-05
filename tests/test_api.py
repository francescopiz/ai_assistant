import os
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Mock environment variables before imports
os.environ["API_BEARER_TOKEN"] = "test_bearer_token_9876"
os.environ["OLLAMA_MODEL"] = "gemma4:26b"
os.environ["OLLAMA_HOST"] = "http://localhost:11434"

from src.api.main import app
from services.database import init_db, get_preference, set_preference
from services.llm_wiki import get_wiki_paths, create_page, read_page, search_wiki

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_test_db_and_wiki():
    # Drop tables to start fresh
    from services.database import Base, engine
    try:
        Base.metadata.drop_all(bind=engine)
    except Exception:
        pass
        
    # Initialize DB
    init_db()
    # Configure test token
    set_preference("BEARER_TOKEN", "test_bearer_token_9876")
    
    # Configure test paths relative to project root
    test_wiki_path = Path(__file__).resolve().parent / "test_data" / "wiki"
    test_raw_path = Path(__file__).resolve().parent / "test_data" / "raw"
    test_assets_path = Path(__file__).resolve().parent / "test_data" / "raw" / "assets"
    
    test_wiki_path.mkdir(parents=True, exist_ok=True)
    test_raw_path.mkdir(parents=True, exist_ok=True)
    test_assets_path.mkdir(parents=True, exist_ok=True)
    
    set_preference("WIKI_PATH", str(test_wiki_path))
    set_preference("RAW_SOURCES_PATH", str(test_raw_path))
    set_preference("ASSETS_PATH", str(test_assets_path))
    
    yield
    
    # Clean up test directories after tests finish
    import shutil
    if test_wiki_path.parent.exists():
        shutil.rmtree(test_wiki_path.parent)

# --- SECURITY / AUTH TESTS ---

def test_root_endpoint_unauthorized():
    response = client.get("/")
    assert response.status_code == 401

def test_root_endpoint_authorized():
    response = client.get("/", headers={"Authorization": "Bearer test_bearer_token_9876"})
    assert response.status_code == 200
    assert response.json()["status"] == "online"

# --- WIKI CRUD SERVICES & ENDPOINTS ---

def test_wiki_crud_functions():
    # Test creation
    res_create = create_page("TestPage", "# Test Title\nThis is a test wiki page.")
    assert "creata con successo" in res_create.lower()
    
    # Test reading
    content = read_page("TestPage")
    assert "# Test Title" in content
    assert "This is a test wiki page." in content
    
    # Test append
    from services.llm_wiki import append_to_page
    res_append = append_to_page("TestPage", "Added paragraph.")
    assert "aggiunto con successo" in res_append.lower()
    
    content_after = read_page("TestPage")
    assert "Added paragraph." in content_after
    
    # Test search
    search_results = search_wiki("Title")
    assert "TestPage" in search_results

def test_wiki_api_endpoints():
    headers = {"Authorization": "Bearer test_bearer_token_9876"}
    
    # Create page via API
    response = client.post(
        "/api/wiki/pages",
        json={"page_name": "APIPage", "content": "# API Page Content"},
        headers=headers
    )
    assert response.status_code == 200
    assert "creata con successo" in response.json()["message"].lower()
    
    # Read page via API
    response = client.get("/api/wiki/pages/APIPage", headers=headers)
    assert response.status_code == 200
    assert response.json()["page_name"] == "APIPage"
    assert response.json()["content"] == "# API Page Content"
    
    # Modify page via API (Append)
    response = client.put(
        "/api/wiki/pages/APIPage",
        json={"action": "append", "content": "Appended via API"},
        headers=headers
    )
    assert response.status_code == 200
    
    # Read page again to verify append
    response = client.get("/api/wiki/pages/APIPage", headers=headers)
    assert "Appended via API" in response.json()["content"]

# --- CONFIG & SCHEDULER TESTS ---

def test_config_api_endpoints():
    headers = {"Authorization": "Bearer test_bearer_token_9876"}
    
    # Get current email schedules
    response = client.get("/api/config/email", headers=headers)
    assert response.status_code == 200
    configs = response.json()
    assert len(configs) >= 2
    
    morning_config = next(c for c in configs if c["email_type"] == "morning")
    assert morning_config["schedule_time"] == "07:00"
    
    # Update email schedule
    response = client.post(
        "/api/config/email",
        json={
            "email_type": "morning",
            "schedule_time": "08:30",
            "enabled": True,
            "active_modules": "weather,news"
        },
        headers=headers
    )
    assert response.status_code == 200
    assert "aggiornata" in response.json()["message"].lower()
    
    # Verify update
    response = client.get("/api/config/email", headers=headers)
    updated_morning = next(c for c in response.json() if c["email_type"] == "morning")
    assert updated_morning["schedule_time"] == "08:30"
    assert updated_morning["active_modules"] == "weather,news"
    
    # Get general preferences
    response = client.get("/api/config/preferences", headers=headers)
    assert response.status_code == 200
    assert response.json()["OLLAMA_MODEL"] == "gemma4:26b"
    
    # Update general preference
    response = client.post(
        "/api/config/preferences",
        json={"key": "TEST_PREF", "value": "test_val"},
        headers=headers
    )
    assert response.status_code == 200
    assert get_preference("TEST_PREF") == "test_val"

# --- AUDIO & DIARY INGEST TESTS (MOCKED) ---

def test_diary_text_entry_endpoint():
    headers = {"Authorization": "Bearer test_bearer_token_9876"}
    
    # Add journal entry directly via text
    response = client.post(
        "/api/audio/add-journal-entry",
        json={"text": "Oggi ho iniziato a programmare il progetto del Secondo Cervello in FastAPI."},
        headers=headers
    )
    assert response.status_code == 200
    assert "avviate in background" in response.json()["message"].lower()

# --- MULTIMODAL QWEN TESTS ---

def test_multimodal_middleware_and_tool():
    import base64
    from services.media_utility import parse_and_attach_media, get_assets_dir
    from services.llm_wiki import analyze_asset
    
    # Create a dummy image asset
    assets_dir = get_assets_dir()
    dummy_img_path = assets_dir / "scontrino.jpg"
    dummy_content = b"dummy_jpeg_data_bytes_12345"
    with open(dummy_img_path, "wb") as f:
        f.write(dummy_content)
        
    # Verify middleware parses it correctly
    b64_list = parse_and_attach_media("Ho speso soldi: ![Ricevuta](../../raw/assets/scontrino.jpg)")
    assert len(b64_list) == 1
    decoded = base64.b64decode(b64_list[0])
    assert decoded == dummy_content
    
    # Verify the tool runs (mock/offline mode)
    tool_res = analyze_asset("scontrino.jpg", "Quanto ho pagato di spesa?")
    assert "15,50" in tool_res
    
    # Verify a missing asset handles gracefully
    err_res = analyze_asset("missing_file.jpg", "descrivi")
    assert "errore" in err_res.lower()

def test_multimodal_api_endpoints():
    headers = {"Authorization": "Bearer test_bearer_token_9876"}
    
    # Test high level upload-asset route
    dummy_file_payload = {"file": ("lavagna.jpg", b"mock_lavagna_visual_data", "image/jpeg")}
    response = client.post("/api/upload-asset", files=dummy_file_payload, headers=headers)
    assert response.status_code == 200
    assert "caricato correttamente" in response.json()["message"].lower()
    assert "/api/wiki/assets/lavagna.jpg" in response.json()["url"]
    
    # Test uploading a visual file to the ingest endpoint /api/audio/upload
    dummy_visual_payload = {"file": ("lavagna.jpg", b"mock_lavagna_visual_data", "image/jpeg")}
    response = client.post("/api/audio/upload", files=dummy_visual_payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["type"] == "visual"
    assert "analisi visiva" in response.json()["message"].lower()
    
    # Test uploading an audio file to the ingest endpoint /api/audio/upload
    dummy_audio_payload = {"file": ("test.mp3", b"mock_audio_bytes", "audio/mpeg")}
    response = client.post("/api/audio/upload", files=dummy_audio_payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["type"] == "audio"
    assert "trascrizione" in response.json()["message"].lower()
