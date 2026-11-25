from fastapi import FastAPI

app = FastAPI(title="CineSense AI Service", version="0.1.0")


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    """Report whether the AI service is responding."""
    return {"status": "ok", "service": "ai"}
