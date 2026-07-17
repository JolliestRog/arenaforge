from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import db
from routers import build, cards, commanders


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    yield
    db.close()


app = FastAPI(
    title="ArenaForge API",
    version="2.0.0",
    root_path="/api",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://deckforge.facey.page"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(cards.router)
app.include_router(commanders.router)
app.include_router(build.router)


@app.get("/health")
def health():
    with db.get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    return {"status": "ok", "cards": count}
