import json

from fastapi import APIRouter, Query

from db import get_db
from models import Commander

router = APIRouter(prefix="/commanders", tags=["commanders"])


@router.get("", response_model=list[Commander])
def list_commanders(
    colors: str | None = Query(None, description="Comma-separated colors the commander must fit within, e.g. U,B"),
    exact: bool = Query(False, description="If true, commander color identity must exactly match the given colors"),
):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT name, cmc, color_identity, type_line, rarity FROM cards WHERE is_commander = 1 ORDER BY name"
        ).fetchall()

    results = []
    for row in rows:
        ci = json.loads(row["color_identity"])
        if colors:
            allowed = set(colors.upper().split(","))
            if exact:
                if set(ci) != allowed:
                    continue
            else:
                if not set(ci).issubset(allowed):
                    continue
        results.append(Commander(
            name=row["name"],
            cmc=row["cmc"],
            color_identity=ci,
            type_line=row["type_line"],
            rarity=row["rarity"],
        ))

    return results
