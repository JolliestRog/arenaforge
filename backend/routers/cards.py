import json

from fastapi import APIRouter, HTTPException, Query

from db import get_db
from models import Card

router = APIRouter(prefix="/cards", tags=["cards"])


def _row_to_card(row) -> Card:
    return Card(
        name=row["name"],
        cmc=row["cmc"],
        mana_cost=row["mana_cost"],
        color_identity=json.loads(row["color_identity"]),
        type_line=row["type_line"],
        rarity=row["rarity"],
        oracle_text=row["oracle_text"],
        keywords=json.loads(row["keywords"]),
        power=row["power"],
        toughness=row["toughness"],
        is_land=bool(row["is_land"]),
        is_creature=bool(row["is_creature"]),
        is_legendary=bool(row["is_legendary"]),
        is_commander=bool(row["is_commander"]),
    )


@router.get("", response_model=list[Card])
def list_cards(
    colors: str | None = Query(None, description="Comma-separated allowed colors, e.g. U,B"),
    min_cmc: float | None = Query(None, ge=0),
    max_cmc: float | None = Query(None, ge=0),
    rarity: str | None = Query(None, description="Comma-separated rarities"),
    is_land: bool | None = Query(None),
    is_creature: bool | None = Query(None),
    q: str | None = Query(None, description="Search in name or oracle text"),
    limit: int = Query(500, ge=1, le=5000),
):
    clauses = []
    params: list = []

    if min_cmc is not None:
        clauses.append("cmc >= ?")
        params.append(min_cmc)
    if max_cmc is not None:
        clauses.append("cmc <= ?")
        params.append(max_cmc)
    if rarity:
        placeholders = ",".join("?" * len(rarity.split(",")))
        clauses.append(f"rarity IN ({placeholders})")
        params.extend(rarity.split(","))
    if is_land is not None:
        clauses.append("is_land = ?")
        params.append(int(is_land))
    if is_creature is not None:
        clauses.append("is_creature = ?")
        params.append(int(is_creature))
    if q:
        clauses.append("(name LIKE ? OR oracle_text LIKE ?)")
        pattern = f"%{q}%"
        params.extend([pattern, pattern])

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM cards {where} ORDER BY name LIMIT ?"
    params.append(limit)

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()

    # Color identity subset filtering: card's CI must be ⊆ allowed colors
    if colors:
        allowed = set(colors.upper().split(","))
        rows = [r for r in rows if set(json.loads(r["color_identity"])).issubset(allowed)]

    return [_row_to_card(r) for r in rows]


@router.get("/{name}", response_model=Card)
def get_card(name: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM cards WHERE name = ?", (name,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return _row_to_card(row)
