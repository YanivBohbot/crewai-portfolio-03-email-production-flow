"""Mock Calendar MCP server. Deuxième service MCP indépendant du premier
(Gmail) — démontre l'orchestration multi-MCP dans un même Flow.

list_free_slots est lecture seule. hold_slot pose un "tentative hold" en
mémoire (process courant uniquement, jamais persisté, jamais un vrai
événement calendrier) — aucune action irréversible, cohérent avec la
politique: aucun agent ne doit réellement bloquer/envoyer sans validation
humaine explicite en amont.
"""

import json

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("calendar-mock")

_FREE_SLOTS = [
    {"slot_id": "slot_thu_14h", "day": "jeudi", "start": "14:00", "end": "14:30"},
    {"slot_id": "slot_thu_16h", "day": "jeudi", "start": "16:00", "end": "16:30"},
    {"slot_id": "slot_fri_10h", "day": "vendredi", "start": "10:00", "end": "10:30"},
]

_tentative_holds: list[str] = []


@mcp.tool()
def list_free_slots() -> str:
    """Liste les créneaux libres cette semaine (lecture seule).

    Retourne un JSON: liste d'objets {slot_id, day, start, end}.
    """
    return json.dumps(_FREE_SLOTS, ensure_ascii=False)


@mcp.tool()
def hold_slot(slot_id: str) -> str:
    """Pose un hold tentatif sur un créneau (réversible, en mémoire seulement).

    N'est PAS une réservation définitive — juste une proposition à inclure
    dans le brouillon de réponse, à valider par un humain avant tout envoi.
    Retourne un JSON {"status": "held", "slot_id": ...} ou {"error": "..."}.
    """
    valid_ids = {s["slot_id"] for s in _FREE_SLOTS}
    if slot_id not in valid_ids:
        return json.dumps({"error": f"slot_id '{slot_id}' inconnu"})
    _tentative_holds.append(slot_id)
    return json.dumps({"status": "held", "slot_id": slot_id})


if __name__ == "__main__":
    mcp.run()
