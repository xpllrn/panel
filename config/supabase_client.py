"""
Supabase client singleton for the project.
Provides access to Supabase API features (storage, auth, realtime, etc.)
while Django ORM handles all database operations through psycopg2.
"""

from django.conf import settings

_client = None


def get_supabase_client():
    """
    Get or create a Supabase client instance.

    Returns the client using the service key for server-side operations.
    Uses the publishable (anon) key if service key is not available.

    Returns:
        supabase.Client: Configured Supabase client
    """
    global _client

    if _client is None:
        from supabase import create_client

        url = settings.SUPABASE_URL
        key = settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_KEY

        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY (or SUPABASE_SERVICE_KEY) " "must be set in .env")

        _client = create_client(url, key)

    return _client
