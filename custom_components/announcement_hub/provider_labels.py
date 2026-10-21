"""Localized labels for dynamic Home Assistant AI provider selections.

Static fields are translated by Home Assistant through translations/*.json.
These dynamic provider labels need to be localized explicitly.
"""
from __future__ import annotations

from typing import Any

LABELS = {
  "en": {
    "preferred": "Preferred Assist pipeline: {name}",
    "built_in": "Preferred Assist pipeline: built-in (not an AI agent)",
    "unavailable": "Preferred Assist pipeline: unavailable",
    "task": "AI Task: {name}",
    "agent_unavailable": "Unavailable agent ({name})",
    "original": "Original announcement (no backup AI)",
    "backup_unavailable": "Unavailable backup agent ({name})",
    "state": "State"
  },
  "el": {
    "preferred": "Προτιμώμενη ροή Assist: {name}",
    "built_in": "Προτιμώμενη ροή Assist: ενσωματωμένη (όχι πράκτορας AI)",
    "unavailable": "Προτιμώμενη ροή Assist: μη διαθέσιμη",
    "task": "Εργασία AI: {name}",
    "agent_unavailable": "Μη διαθέσιμος πράκτορας ({name})",
    "original": "Αρχική ανακοίνωση (χωρίς εφεδρικό AI)",
    "backup_unavailable": "Μη διαθέσιμος εφεδρικός πράκτορας ({name})",
    "state": "Κατάσταση"
  },
  "de": {
    "preferred": "Bevorzugte Assist-Pipeline: {name}",
    "built_in": "Bevorzugte Assist-Pipeline: integriert (kein KI-Agent)",
    "unavailable": "Bevorzugte Assist-Pipeline: nicht verfügbar",
    "task": "KI-Aufgabe: {name}",
    "agent_unavailable": "Agent nicht verfügbar ({name})",
    "original": "Originalankündigung (ohne Ersatz-KI)",
    "backup_unavailable": "Ersatzagent nicht verfügbar ({name})",
    "state": "Zustand"
  },
  "fr": {
    "preferred": "Pipeline Assist préférée : {name}",
    "built_in": "Pipeline Assist préférée : intégrée (pas un agent IA)",
    "unavailable": "Pipeline Assist préférée : indisponible",
    "task": "Tâche IA : {name}",
    "agent_unavailable": "Agent indisponible ({name})",
    "original": "Annonce d'origine (sans IA de secours)",
    "backup_unavailable": "Agent de secours indisponible ({name})",
    "state": "État"
  },
  "es": {
    "preferred": "Canal Assist preferido: {name}",
    "built_in": "Canal Assist preferido: integrado (no es agente de IA)",
    "unavailable": "Canal Assist preferido: no disponible",
    "task": "Tarea de IA: {name}",
    "agent_unavailable": "Agente no disponible ({name})",
    "original": "Anuncio original (sin IA de respaldo)",
    "backup_unavailable": "Agente de respaldo no disponible ({name})",
    "state": "Estado"
  },
  "it": {
    "preferred": "Pipeline Assist preferita: {name}",
    "built_in": "Pipeline Assist preferita: integrata (non è un agente IA)",
    "unavailable": "Pipeline Assist preferita: non disponibile",
    "task": "Attività IA: {name}",
    "agent_unavailable": "Agente non disponibile ({name})",
    "original": "Annuncio originale (senza IA di riserva)",
    "backup_unavailable": "Agente di riserva non disponibile ({name})",
    "state": "Stato"
  },
  "pt": {
    "preferred": "Pipeline Assist preferida: {name}",
    "built_in": "Pipeline Assist preferida: integrada (não é agente IA)",
    "unavailable": "Pipeline Assist preferida: indisponível",
    "task": "Tarefa IA: {name}",
    "agent_unavailable": "Agente indisponível ({name})",
    "original": "Anúncio original (sem IA alternativa)",
    "backup_unavailable": "Agente alternativo indisponível ({name})",
    "state": "Estado"
  },
  "pt-BR": {
    "preferred": "Pipeline Assist preferida: {name}",
    "built_in": "Pipeline Assist preferida: integrada (não é agente de IA)",
    "unavailable": "Pipeline Assist preferida: indisponível",
    "task": "Tarefa de IA: {name}",
    "agent_unavailable": "Agente indisponível ({name})",
    "original": "Anúncio original (sem IA alternativa)",
    "backup_unavailable": "Agente alternativo indisponível ({name})",
    "state": "Estado"
  },
  "nl": {
    "preferred": "Voorkeurs-Assist-pipeline: {name}",
    "built_in": "Voorkeurs-Assist-pipeline: ingebouwd (geen AI-agent)",
    "unavailable": "Voorkeurs-Assist-pipeline: niet beschikbaar",
    "task": "AI-taak: {name}",
    "agent_unavailable": "Agent niet beschikbaar ({name})",
    "original": "Oorspronkelijke aankondiging (geen reserve-AI)",
    "backup_unavailable": "Reserveagent niet beschikbaar ({name})",
    "state": "Status"
  },
  "pl": {
    "preferred": "Preferowany potok Assist: {name}",
    "built_in": "Preferowany potok Assist: wbudowany (nie jest agentem AI)",
    "unavailable": "Preferowany potok Assist: niedostępny",
    "task": "Zadanie AI: {name}",
    "agent_unavailable": "Agent niedostępny ({name})",
    "original": "Oryginalne ogłoszenie (bez zapasowej AI)",
    "backup_unavailable": "Zapasowy agent niedostępny ({name})",
    "state": "Stan"
  },
  "ru": {
    "preferred": "Предпочтительный конвейер Assist: {name}",
    "built_in": "Предпочтительный Assist: встроенный (не ИИ-агент)",
    "unavailable": "Предпочтительный Assist: недоступен",
    "task": "Задача ИИ: {name}",
    "agent_unavailable": "Агент недоступен ({name})",
    "original": "Исходное объявление (без резервного ИИ)",
    "backup_unavailable": "Резервный агент недоступен ({name})",
    "state": "Состояние"
  },
  "tr": {
    "preferred": "Tercih edilen Assist hattı: {name}",
    "built_in": "Tercih edilen Assist hattı: yerleşik (YZ aracısı değil)",
    "unavailable": "Tercih edilen Assist hattı: kullanılamıyor",
    "task": "YZ görevi: {name}",
    "agent_unavailable": "Aracı kullanılamıyor ({name})",
    "original": "Özgün duyuru (yedek YZ olmadan)",
    "backup_unavailable": "Yedek aracı kullanılamıyor ({name})",
    "state": "Durum"
  },
  "uk": {
    "preferred": "Основний конвеєр Assist: {name}",
    "built_in": "Основний Assist: вбудований (не агент ШІ)",
    "unavailable": "Основний Assist: недоступний",
    "task": "Завдання ШІ: {name}",
    "agent_unavailable": "Агент недоступний ({name})",
    "original": "Початкове оголошення (без резервного ШІ)",
    "backup_unavailable": "Резервний агент недоступний ({name})",
    "state": "Стан"
  },
  "ar": {
    "preferred": "مسار Assist المفضل: {name}",
    "built_in": "مسار Assist المفضل: مدمج (ليس وكيل ذكاء اصطناعي)",
    "unavailable": "مسار Assist المفضل: غير متاح",
    "task": "مهمة ذكاء اصطناعي: {name}",
    "agent_unavailable": "الوكيل غير متاح ({name})",
    "original": "الإعلان الأصلي (من دون ذكاء اصطناعي بديل)",
    "backup_unavailable": "الوكيل البديل غير متاح ({name})",
    "state": "الحالة"
  },
  "zh-Hans": {
    "preferred": "首选 Assist 流程：{name}",
    "built_in": "首选 Assist 流程：内置（非 AI 代理）",
    "unavailable": "首选 Assist 流程：不可用",
    "task": "AI 任务：{name}",
    "agent_unavailable": "代理不可用（{name}）",
    "original": "原始公告（无备用 AI）",
    "backup_unavailable": "备用代理不可用（{name}）",
    "state": "状态"
  },
  "zh-Hant": {
    "preferred": "首選 Assist 流程：{name}",
    "built_in": "首選 Assist 流程：內建（非 AI 代理）",
    "unavailable": "首選 Assist 流程：無法使用",
    "task": "AI 任務：{name}",
    "agent_unavailable": "代理無法使用（{name}）",
    "original": "原始公告（無備用 AI）",
    "backup_unavailable": "備用代理無法使用（{name}）",
    "state": "狀態"
  },
  "ja": {
    "preferred": "優先する Assist パイプライン: {name}",
    "built_in": "優先する Assist: 組み込み（AIエージェントではありません）",
    "unavailable": "優先する Assist: 利用不可",
    "task": "AIタスク: {name}",
    "agent_unavailable": "利用できないエージェント（{name}）",
    "original": "元のアナウンス（予備AIなし）",
    "backup_unavailable": "予備エージェントは利用不可（{name}）",
    "state": "状態"
  },
  "ko": {
    "preferred": "기본 Assist 파이프라인: {name}",
    "built_in": "기본 Assist: 내장형(AI 에이전트 아님)",
    "unavailable": "기본 Assist: 사용할 수 없음",
    "task": "AI 작업: {name}",
    "agent_unavailable": "사용할 수 없는 에이전트({name})",
    "original": "원본 안내(예비 AI 없음)",
    "backup_unavailable": "예비 에이전트를 사용할 수 없음({name})",
    "state": "상태"
  },
  "sv": {
    "preferred": "Föredragen Assist-pipeline: {name}",
    "built_in": "Föredragen Assist-pipeline: inbyggd (inte AI-agent)",
    "unavailable": "Föredragen Assist-pipeline: otillgänglig",
    "task": "AI-uppgift: {name}",
    "agent_unavailable": "Agent otillgänglig ({name})",
    "original": "Originalmeddelande (utan reserv-AI)",
    "backup_unavailable": "Reservagent otillgänglig ({name})",
    "state": "Tillstånd"
  },
  "cs": {
    "preferred": "Preferované prostředí Assist: {name}",
    "built_in": "Preferované Assist: vestavěné (nejde o agenta AI)",
    "unavailable": "Preferované Assist: nedostupné",
    "task": "Úloha AI: {name}",
    "agent_unavailable": "Agent není dostupný ({name})",
    "original": "Původní oznámení (bez záložní AI)",
    "backup_unavailable": "Záložní agent není dostupný ({name})",
    "state": "Stav"
  }
}


def provider_label(hass: Any, key: str, **values: str) -> str:
    """Render an AI choice label, preferring HA's configured locale."""
    raw = str(getattr(getattr(hass, "config", None), "language", "en") or "en").replace("_", "-")
    if raw.lower().startswith(("zh-tw", "zh-hk", "zh-hant")):
        locale = "zh-Hant"
    elif raw.lower().startswith("zh"):
        locale = "zh-Hans"
    elif raw.lower().startswith("pt-br"):
        locale = "pt-BR"
    else:
        locale = raw.split("-", 1)[0].lower()
    template = LABELS.get(locale, LABELS["en"]).get(key, LABELS["en"][key])
    return template.format(**values)
