from typing import Any, Tuple

from pydantic import BaseModel

from crewai import Agent, Crew, Process, Task
from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource
from crewai.memory import Memory
from crewai.project import CrewBase, agent, crew, task
from crewai.tasks.task_output import TaskOutput


class DraftEmail(BaseModel):
    to: str
    subject: str
    body: str


# Politiques internes mock — en prod: PDFKnowledgeSource / CSVKnowledgeSource
# pointant vers les vrais documents RH/support dans knowledge/.
SUPPORT_POLICIES = StringKnowledgeSource(
    content="""
    Politique Facturation §1: Toute facture impayée après 30 jours génère une relance écrite automatique.
    Politique Facturation §2: Une suspension de service ne peut intervenir qu'après 2 relances écrites, jamais sur la première notification.

    Politique Support Technique §1: Un bug qualifié "critique en production" reçoit un accusé de réception sous 2h ouvrées.
    Politique Support Technique §2: Toute régression impactant un client final est escaladée automatiquement au lead technique.

    Politique Réunions Partenariat §1: Les demandes de créneau partenariat sont honorées sous 48h avec au moins 2 propositions de créneau.
    """
)


def require_policy_citation(result: TaskOutput) -> Tuple[bool, Any]:
    """Guardrail anti-hallucination: refuse tout brouillon sans référence de
    politique citée, ou qui prétend que l'email a déjà été envoyé."""
    raw_lower = result.raw.lower()
    if "politique" not in raw_lower:
        return (False, "VALIDATION_ERROR: le brouillon doit citer la référence de politique interne utilisée")
    if "a été envoyé" in raw_lower or "email envoyé" in raw_lower:
        return (False, "VALIDATION_ERROR: ne jamais affirmer que l'email a été envoyé — c'est un brouillon")
    return (True, result.raw)


@CrewBase
class EmailCrew:
    """Crew sequential: trouve la politique applicable, rédige un brouillon."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def policy_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["policy_analyst"],  # type: ignore[index]
            knowledge_sources=[SUPPORT_POLICIES],
            embedder={"provider": "openai", "config": {"model": "text-embedding-3-small"}},
        )

    @agent
    def drafter(self) -> Agent:
        return Agent(config=self.agents_config["drafter"])  # type: ignore[index]

    @task
    def find_policy_task(self) -> Task:
        return Task(config=self.tasks_config["find_policy_task"])  # type: ignore[index]

    @task
    def draft_reply_task(self) -> Task:
        return Task(
            config=self.tasks_config["draft_reply_task"],  # type: ignore[index]
            context=[self.find_policy_task()],
            guardrail=require_policy_citation,
            guardrail_max_retries=3,
            output_pydantic=DraftEmail,
        )

    @crew
    def crew(self) -> Crew:
        memory = Memory(
            importance_weight=0.4,
            recency_weight=0.3,
            semantic_weight=0.3,
            recency_half_life_days=180,  # politiques internes stables, pas d'actu éphémère
        )
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            memory=memory,
            verbose=True,
        )
