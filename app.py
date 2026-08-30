"""Hugging Face Space entry point for Cella FastAPI backend."""

from __future__ import annotations

import os
import uvicorn
from cella.api.main import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
