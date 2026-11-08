import os
from functools import lru_cache
from typing import Optional

try:
    from supabase import Client, create_client
except ImportError:
    Client = None
    create_client = None


@lru_cache(maxsize=1)
def get_supabase_client() -> Optional["Client"]:
    """
    Returns a cached instance of the Supabase client using credentials
    from settings or environment variables.
    """
    if create_client is None:
        return None

    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")

    if not url or not key:
        return None

    return create_client(url, key)
