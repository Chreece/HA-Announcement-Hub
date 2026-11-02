"""Read-only catalogue of configured AI and speech providers for the card.

Constructed on demand from Home Assistant's own entities, registered
Conversation agents, and enabled TTS engines. No credentials, prompts,
message bodies, or config-entry data are returned.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def build_provider_catalog(
    conversation_states: Iterable[Any],
    ai_task_states: Iterable[Any],
    conversation_agents: Iterable[Any],
    tts_options: Iterable[Mapping[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    """Merge provider inventories without losing entity-free Conversation agents."""
    ai: dict[str, str] = {"default": "Home Assistant preferred agent"}

    def state_name(state: Any) -> str:
        attrs = getattr(state, "attributes", None) or {}
        label = attrs.get("friendly_name") if isinstance(attrs, Mapping) else None
        return str(label or getattr(state, "name", None) or getattr(state, "entity_id", ""))

    for states, prefix, kind in (
        (conversation_states, "conversation.", "Conversation"),
        (ai_task_states, "ai_task.", "AI Task"),
    ):
        for state in states:
            entity_id = str(getattr(state, "entity_id", "") or "")
            if not entity_id.startswith(prefix):
                continue
            ai.setdefault(entity_id, f"{state_name(state)} · {kind} · {entity_id}")

    for agent in conversation_agents:
        agent_id = str(
            (agent.get("id") if isinstance(agent, Mapping) else getattr(agent, "id", None)) or ""
        )
        if not agent_id or agent_id in ai:
            continue
        name = agent.get("name") if isinstance(agent, Mapping) else getattr(agent, "name", None)
        ai[agent_id] = f"{str(name or agent_id)} · Conversation"

    speech: dict[str, str] = {}
    for choice in tts_options:
        entity_id = str(choice.get("value", "") or "")
        if not entity_id.startswith("tts."):
            continue
        # TTS entity options may include a long list of languages. The card
        # needs only "Integration – TTS entity name" to remain compact.
        raw_label = str(choice.get("label") or entity_id)
        parts = raw_label.split(" · ")
        short_label = " – ".join(parts[:2]) if len(parts) > 1 else "TTS – " + raw_label
        speech.setdefault(entity_id, short_label)

    def sorted_choices(values: Mapping[str, str]) -> list[dict[str, str]]:
        return [
            {"value": value, "label": label}
            for value, label in sorted(values.items(), key=lambda item: (item[1].casefold(), item[0]))
        ]

    ai_choices = [{"value": "default", "label": ai.pop("default")}]
    ai_choices.extend(sorted_choices(ai))
    return {"ai_agents": ai_choices, "tts_engines": sorted_choices(speech)}
