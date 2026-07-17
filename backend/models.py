from pydantic import BaseModel


class Card(BaseModel):
    name: str
    cmc: float
    mana_cost: str | None
    color_identity: list[str]
    type_line: str
    rarity: str
    oracle_text: str
    keywords: list[str]
    power: str | None
    toughness: str | None
    is_land: bool
    is_creature: bool
    is_legendary: bool
    is_commander: bool


class Commander(BaseModel):
    name: str
    cmc: float
    color_identity: list[str]
    type_line: str
    rarity: str
