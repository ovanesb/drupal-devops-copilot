"""Core package for Drupal DevOps Co-Pilot."""
__version__ = "0.1.0"

try:
    from pathlib import Path
    from dotenv import load_dotenv
    repo_root_env = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(dotenv_path=repo_root_env, override=False)
    load_dotenv(override=False)
except Exception:
    pass
