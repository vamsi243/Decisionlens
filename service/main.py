"""FastAPI entry point for the Decision Lens stream service."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from service.settings import get_settings

app = FastAPI(title="Decision Lens", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "run_mode": get_settings().run_mode}


@app.get("/")
def hello() -> dict[str, str]:
    return {"message": "Decision Lens: every moment, every option, every fan."}
