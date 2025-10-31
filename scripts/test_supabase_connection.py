#!/usr/bin/env python3
"""
Test Supabase connection and verify environment setup
"""
import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

def test_connection():
    """Test Supabase connection"""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        print("❌ Missing SUPABASE_URL or SUPABASE_KEY in .env")
        return False

    # Add https:// prefix if missing
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    print(f"🔗 Connecting to Supabase...")
    print(f"URL: {url[:50]}...")

    try:
        client: Client = create_client(url, key)

        # Test query - list tables
        result = client.table("_supabase_migrations").select("*").limit(1).execute()

        print("✅ Successfully connected to Supabase!")
        print(f"Connection test passed")
        return True

    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
