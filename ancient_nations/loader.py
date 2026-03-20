"""
loader.py – JSON5 file loader using the json5 package.
Install: pip install json5  (or: uv add json5)
"""
import json5
from pathlib import Path


def load_json5(path):
    """Load a JSON5 file and return parsed Python object."""
    return json5.load(open(Path(path), encoding='utf-8'))
