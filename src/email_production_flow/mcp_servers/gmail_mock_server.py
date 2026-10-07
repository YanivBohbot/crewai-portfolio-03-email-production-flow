"""Mock Gmail MCP server. Lecture seule — aucun tool send/delete exposé.

Sert de remplaçant local au vrai Gmail MCP (OAuth) pour développer et tester
l'architecture agent + MCP sans configurer Google Cloud Console. Les tools
exposés ici (list_recent_emails, get_email) ont la même forme que ceux d'un
vrai serveur Gmail MCP, donc remplacer ce module par un serveur OAuth réel
plus tard ne change rien côté agent.
"""

import json

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("gmail-mock")

_INBOX = {
    "msg_001": {
        "id": "msg_001",
        "sender": "facturation@hebergeur-cloud.com",
        "subject": "URGENT: facture impayée, suspension compte dans 24h",
        "received_at": "2026-10-07T08:12:00",
        "body": "Votre facture #4471 de 340 EUR est impayée depuis 15 jours. "
        "Sans règlement dans les 24h, le service sera suspendu.",
    },
    "msg_002": {
        "id": "msg_002",
        "sender": "j.martin@client-acme.com",
        "subject": "Re: Bug critique en prod sur l'export CSV",
        "received_at": "2026-10-07T07:45:00",
        "body": "Le bug bloque toute l'équipe depuis ce matin, export CSV renvoie "
        "une erreur 500. Besoin d'un retour rapide, impact client final.",
    },
    "msg_003": {
        "id": "msg_003",
        "sender": "newsletter@techdigest.io",
        "subject": "5 tendances IA à suivre cette semaine",
        "received_at": "2026-10-06T19:00:00",
        "body": "Notre sélection hebdomadaire des actus IA...",
    },
    "msg_004": {
        "id": "msg_004",
        "sender": "sophie.durand@partenaire.com",
        "subject": "Proposition créneau réunion partenariat",
        "received_at": "2026-10-07T09:30:00",
        "body": "Seriez-vous disponible jeudi ou vendredi pour discuter du "
        "partenariat Q4? 30 minutes suffisent.",
    },
    "msg_005": {
        "id": "msg_005",
        "sender": "security-noreply@github.com",
        "subject": "Nouvelle connexion détectée depuis un appareil inconnu",
        "received_at": "2026-10-07T06:02:00",
        "body": "Une connexion à votre compte a eu lieu depuis une nouvelle "
        "localisation. Si ce n'était pas vous, sécurisez votre compte.",
    },
    "msg_006": {
        "id": "msg_006",
        "sender": "no-reply@livraison-colis.com",
        "subject": "Votre colis a été livré",
        "received_at": "2026-10-06T14:20:00",
        "body": "Votre colis a été déposé devant la porte à 14h20.",
    },
}


@mcp.tool()
def list_recent_emails(limit: int = 10) -> str:
    """Liste les emails récents de la boîte de réception (lecture seule).

    Retourne un JSON: liste d'objets {id, sender, subject, received_at}.
    N'inclut pas le corps du message — utiliser get_email pour le détail.
    """
    items = list(_INBOX.values())[:limit]
    summary = [
        {"id": e["id"], "sender": e["sender"], "subject": e["subject"], "received_at": e["received_at"]}
        for e in items
    ]
    return json.dumps(summary, ensure_ascii=False)


@mcp.tool()
def get_email(email_id: str) -> str:
    """Récupère le contenu complet d'un email par son id (lecture seule).

    Retourne un JSON: {id, sender, subject, received_at, body}, ou une erreur
    JSON {"error": "..."} si l'id est inconnu.
    """
    email = _INBOX.get(email_id)
    if email is None:
        return json.dumps({"error": f"email_id '{email_id}' introuvable"})
    return json.dumps(email, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
