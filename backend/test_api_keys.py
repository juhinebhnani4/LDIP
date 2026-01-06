"""Test all API keys and services"""
import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv(".env.local")

def test_redis():
    """Test Redis connection"""
    print("\n[REDIS] Testing...")
    try:
        import redis
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        r.ping()
        print("   [OK] Redis: Connected")
        return True
    except Exception as e:
        print(f"   [FAIL] Redis: {e}")
        return False

def test_supabase():
    """Test Supabase connection"""
    print("\n[SUPABASE] Testing...")
    try:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        client = create_client(url, key)
        # Try a simple query
        client.table("matters").select("id").limit(1).execute()
        print("   [OK] Supabase: Connected")
        return True
    except Exception as e:
        print(f"   [FAIL] Supabase: {e}")
        return False

def test_openai():
    """Test OpenAI API key"""
    print("\n[OPENAI] Testing...")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.models.list()
        print("   [OK] OpenAI: Valid API key")
        return True
    except Exception as e:
        print(f"   [FAIL] OpenAI: {e}")
        return False

def test_google_gemini():
    """Test Google Gemini API key"""
    print("\n[GEMINI] Testing...")
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        models = genai.list_models()
        list(models)[:1]
        print("   [OK] Google Gemini: Valid API key")
        return True
    except Exception as e:
        print(f"   [FAIL] Google Gemini: {e}")
        return False

def test_google_document_ai():
    """Test Google Document AI"""
    print("\n[DOCUMENT AI] Testing...")
    try:
        from google.cloud import documentai_v1 as documentai
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us")
        
        creds_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_file and not os.path.isabs(creds_file):
            creds_file = os.path.join(os.getcwd(), creds_file)
        
        if not creds_file or not os.path.exists(creds_file):
            print(f"   [FAIL] Document AI: Credentials file not found: {creds_file}")
            return False
            
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_file
        
        client = documentai.DocumentProcessorServiceClient()
        parent = client.common_location_path(project_id, location)
        list(client.list_processors(parent=parent))
        print("   [OK] Google Document AI: Connected")
        return True
    except Exception as e:
        print(f"   [FAIL] Google Document AI: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("LDIP API Keys Test")
    print("=" * 50)
    
    results = []
    results.append(("Redis", test_redis()))
    results.append(("Supabase", test_supabase()))
    results.append(("OpenAI", test_openai()))
    results.append(("Google Gemini", test_google_gemini()))
    results.append(("Google Document AI", test_google_document_ai()))
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[OK] PASS" if result else "[X] FAIL"
        print(f"   {name}: {status}")
    
    print(f"\n   Total: {passed}/{total} services connected")
    print("=" * 50)
    
    sys.exit(0 if passed == total else 1)
