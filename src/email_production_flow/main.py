#!/usr/bin/env python
import json
import os
import sys

from pydantic import BaseModel, Field

from crewai import Agent
from crewai.flow import Flow, human_feedback, listen, or_, persist, router, start
from crewai.mcp import MCPServerStdio

from email_production_flow.crews.email_crew.email_crew import DraftEmail, EmailCrew
from email_production_flow.mcp_servers.gmail_mock_server import get_email

MODEL = os.environ.get("MODEL", "openai/gpt-4.1-mini")

MEETING_KEYWORDS = ("réunion", "creneau", "créneau", "partenariat", "rendez-vous")


class EmailClassification(BaseModel):
    email_id: str = Field(description="l'id exact renvoyé par le tool, ex: 'msg_001' — copié tel quel, jamais reformulé")
    sender: str
    priority: str = Field(description="urgent, normal ou spam")
    summary: str = Field(description="résumé en une phrase")


class TriageReport(BaseModel):
    emails: list[EmailClassification]


class ProductionState(BaseModel):
    current_step: str = ""
    report: TriageReport | None = None
    sender: str = ""
    subject: str = ""
    body: str = ""
    meeting_slot: str = ""
    draft: DraftEmail | None = None
    approved: bool = False


@persist()
class EmailProductionFlow(Flow[ProductionState]):

    @start()
    def triage_inbox(self):
        self.state.current_step = "triage_inbox"

        gmail_mcp = MCPServerStdio(
            command=sys.executable,
            args=["-m", "email_production_flow.mcp_servers.gmail_mock_server"],
        )

        triage_agent = Agent(
            role="Email Triage Specialist",
            goal="Lire les emails récents et les classer par priorité, sans jamais répondre ni supprimer",
            backstory=(
                "Assistant prudent et méthodique. Ne fait que lire et classer : "
                "liste les emails récents puis récupère le détail de chacun avant de juger la priorité."
            ),
            mcps=[gmail_mcp],
            llm=MODEL,
            verbose=True,
        )

        result = triage_agent.kickoff(
            "Liste les emails récents de la boîte, récupère le détail de chacun, "
            "puis classe-les par priorité (urgent, normal, spam) avec un résumé. "
            "Important: email_id doit être copié exactement depuis le champ 'id' "
            "renvoyé par les tools (ex: 'msg_001'), jamais reformulé ou deviné.",
            response_format=TriageReport,
        )

        self.state.report = result.pydantic

        urgent = [e for e in self.state.report.emails if e.priority == "urgent"]
        candidates = urgent if urgent else self.state.report.emails

        email_detail = None
        for candidate in candidates:
            detail = json.loads(get_email(email_id=candidate.email_id))
            if "error" not in detail:
                email_detail = detail
                break

        if email_detail is None:
            raise ValueError(
                f"Aucun email_id valide trouvé parmi {[c.email_id for c in candidates]}"
            )

        self.state.sender = email_detail["sender"]
        self.state.subject = email_detail["subject"]
        self.state.body = email_detail["body"]

    @router(triage_inbox)
    def route_by_category(self):
        text = f"{self.state.subject} {self.state.body}".lower()
        if any(keyword in text for keyword in MEETING_KEYWORDS):
            return "needs_meeting"
        return "simple_reply"

    @listen("needs_meeting")
    def propose_slot(self):
        self.state.current_step = "propose_slot"

        calendar_mcp = MCPServerStdio(
            command=sys.executable,
            args=["-m", "email_production_flow.mcp_servers.calendar_mock_server"],
        )

        scheduler_agent = Agent(
            role="Scheduler Assistant",
            goal="Proposer un créneau libre et poser un hold tentatif, jamais une réservation définitive",
            backstory="Assistant prudent. Ne pose que des holds tentatifs, réversibles, jamais de vraie réservation.",
            mcps=[calendar_mcp],
            llm=MODEL,
            verbose=True,
        )

        result = scheduler_agent.kickoff(
            "Liste les créneaux libres, choisis-en un, pose un hold tentatif dessus, "
            "puis décris le créneau choisi en une phrase (jour + heure)."
        )

        self.state.meeting_slot = result.raw

    @listen("simple_reply")
    def skip_meeting(self):
        self.state.meeting_slot = ""

    @listen(or_(propose_slot, skip_meeting))
    @human_feedback(
        message="Valider ce brouillon avant envoi réel ?",
        emit=["approved", "rejected"],
        llm=MODEL,
        default_outcome="rejected",
    )
    def draft_reply(self):
        self.state.current_step = "draft_reply"

        result = EmailCrew().crew().kickoff(
            inputs={
                "sender": self.state.sender,
                "subject": self.state.subject,
                "body": self.state.body,
                "meeting_slot": self.state.meeting_slot,
            }
        )

        self.state.draft = result.pydantic
        return self.state.draft.body

    @listen("approved")
    def finalize_approved(self):
        self.state.current_step = "approved"
        self.state.approved = True

    @listen("rejected")
    def finalize_rejected(self):
        self.state.current_step = "rejected"
        self.state.approved = False


def kickoff():
    flow = EmailProductionFlow()
    flow.kickoff()

    print("\n=== RAPPORT DE TRIAGE ===")
    for email in flow.state.report.emails:
        print(f"[{email.priority.upper():6}] {email.sender} — {email.summary}")

    if flow.state.meeting_slot:
        print(f"\n=== CRÉNEAU PROPOSÉ === \n{flow.state.meeting_slot}")

    if flow.state.draft:
        print("\n=== BROUILLON DE RÉPONSE ===")
        print(f"À: {flow.state.draft.to}")
        print(f"Sujet: {flow.state.draft.subject}")
        print(flow.state.draft.body)

    print(f"\n=== DÉCISION HUMAINE: {'APPROUVÉ' if flow.state.approved else 'REJETÉ'} ===")


def plot():
    flow = EmailProductionFlow()
    flow.plot()


if __name__ == "__main__":
    kickoff()
