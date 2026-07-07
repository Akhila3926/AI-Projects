from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import ingest, review, outputs

app = FastAPI(title="AI Denial Management Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(review.router)
app.include_router(outputs.router)


@app.get("/health")
def health():
    return {"status": "ok"}
