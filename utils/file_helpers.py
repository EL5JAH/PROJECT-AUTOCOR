"""
Read files (YAML, JSON, text)
Write files (artifacts, logs, outputs)
Handle paths cleanly
Create directories safely
Timestamp helpers (for artifacts)

✅ What SHOULD live here
Anything that touches disk
Anything that formats data for disk
Anything that standardizes paths
"""
import os
import yaml
import json
from datetime import datetime
from pathlib import Path

def load_yaml(file_path: str) -> dict:
    """Load a YAML file and return as dict."""
    try:
        with open(file_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        raise RuntimeError(f"Failed to load YAML file: {file_path}") from e
    
def save_yaml(data: dict, file_path: str) -> None:
    """Write dict to YAML file."""
    try:
        with open(file_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
    except Exception as e:
        raise RuntimeError(f"Failed to write YAML file: {file_path}") from e
    
def load_json(file_path: str) -> dict:
    """Load JSON file."""
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"Failed to load JSON file: {file_path}") from e
    
def save_json(data: dict, file_path: str) -> None:
    """Write dict to JSON file."""
    try:
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        raise RuntimeError(f"Failed to write JSON file: {file_path}") from e
    
def ensure_dir(path: str) -> None:
    """Create directory if it doesn't exist."""
    Path(path).mkdir(parents=True, exist_ok=True)

def get_timestamp() -> str:
    """Return formatted timestamp for file naming."""
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def build_run_dir(base_path="artifacts/runs") -> str:
    """
    Create and return a timestamped run directory.
    Example: artifacts/runs/20260410-153022/
    """
    timestamp = get_timestamp()
    run_path = os.path.join(base_path, timestamp)
    ensure_dir(run_path)
    return run_path

def write_text(file_path: str, content: str) -> None:
    """Write raw text to file."""
    try:
        with open(file_path, "w") as f:
            f.write(content)
    except Exception as e:
        raise RuntimeError(f"Failed to write text file: {file_path}") from e
    
def append_text(file_path: str, content: str) -> None:
    """Append text to file."""
    try:
        with open(file_path, "a") as f:
            f.write(content + "\n")
    except Exception as e:
        raise RuntimeError(f"Failed to append to file: {file_path}") from e