"""Talk to NIRVAAN: one conversational turn, end to end.

Pipeline (the same rules as everywhere else in NIRVAAN):
1. screen the input (credentials are masked and never forwarded; requests for
   buy/sell/hold decisions or predictions get the guardrail answer),
2. ask the provider registry (local model first, deterministic fallback),
3. screen the output before it reaches the person,
4. shape a contextual explanation panel from the answer,
5. record the turn - with text only if the person allows transcript storage.

The reply is always in the language the person selected. When no model is
available the fallback answers come from reviewed templates in that language
(``app.services.talk_answers``).
"""
from __future__ import annotations

import hashlib
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

from app.models.user import User
from app.models.voice import VoiceMessage, VoiceSession
from app.services import cache, i18n
from app.services import responsible_ai as rai
from app.services import talk_answers
from app.services.ai import local_provider
from app.services.ai.base import Message
from app.services.ai.registry import registry

MAX_INPUT_CHARS = 1000

# Identical general questions answered by a real model are reused for an hour
# (shared across workers when Redis is on). Only short, impersonal,
# guardrail-clean questions qualify - see ``_cache_key``.
ANSWER_CACHE_TTL = 3600
_CACHE_MAX_CHARS = 200
# Anything that looks personal keeps the answer out of the shared cache:
# numbers (amounts, account/phone digits), emails, first-person words.
_PERSONAL = re.compile(
    r"\d{3,}|@|\b(my|mine|me|i|i'm|i've|we|our|us)\b"
    r"|मेरा|मेरी|मेरे|मुझे|मैं|हम|हमारा"
    r"|என்|எனக்கு|நான்|நாங்கள்|எங்கள்",
    re.IGNORECASE,
)

_GUARDRAIL_INTENTS = {"advice_request", "price_prediction"}

_ADVICE_LOCAL = re.compile(
    r"(खरीद|बेच|निवेश).*(चाहिए|करूँ|करूं|करना ठीक)"
    r"|(வாங்க|விற்க|முதலீடு).*(வேண்டுமா|செய்யலாமா|நல்லதா)"
)

_CREDENTIAL_REPLY = {
    "hi": (
        "आपके संदेश में पासवर्ड, OTP, PIN या कार्ड जैसी जानकारी दिखी, इसलिए मैंने उसे हटा दिया है "
        "और सेव नहीं किया।\n\n"
        "कृपया यह किसी को न बताएँ, मुझे भी नहीं। कोई बैंक, ब्रोकर, नियामक या सरकारी दफ़्तर "
        "इसे कभी नहीं माँगता।\n\n"
        "अगर आपने किसी को बता दिया है, तो अपने कार्ड या पासबुक पर छपे नंबर से बैंक को कॉल करें "
        "और हाल के लेन-देन रोकने और जाँचने को कहें।"
    ),
    "ta": (
        "உங்கள் மெசேஜில் பாஸ்வேர்டு, OTP, PIN அல்லது கார்டு விவரம் போன்றது தெரிந்தது; அதை நீக்கிவிட்டேன், "
        "சேமிக்கவில்லை.\n\n"
        "தயவுசெய்து இதை யாரிடமும் பகிராதீர்கள், என்னிடமும் கூட. எந்த வங்கியும், புரோக்கரும், அரசு அலுவலகமும் "
        "இதை ஒருபோதும் கேட்காது.\n\n"
        "ஏற்கனவே பகிர்ந்திருந்தால், உங்கள் கார்டு அல்லது பாஸ்புக்கில் உள்ள எண்ணில் வங்கியை அழைத்து "
        "சமீபத்திய பரிவர்த்தனைகளை நிறுத்தச் சொல்லுங்கள்."
    ),
}

_QUESTION_START = re.compile(
    r"^\s*(what|how|why|is|are|can|should|does|do|when|where|which|who|explain|tell me)\b"
    r"|क्या|कैसे|क्यों|कब|कौन|बताइए|समझाइए"
    r"|என்ன|எப்படி|ஏன்|எது|யார்|விளக்க",
    re.IGNORECASE,
)


@dataclass
class Turn:
    reply: str
    language: str
    intent: str | None
    panel: dict[str, Any]
    provider: str
    offline: bool
    guardrail: str
    session_id: str
    retained: bool
    notes: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "reply": self.reply,
            "language": self.language,
            "intent": self.intent,
            "panel": self.panel,
            "provider": self.provider,
            "offline": self.offline,
            "guardrail": self.guardrail,
            "session_id": self.session_id,
            "retained": self.retained,
        }


def _intent(text: str) -> str | None:
    if _ADVICE_LOCAL.search(text):
        return "advice_request"
    # Multilingual patterns first so "SIP" is not folded into mutual funds.
    return talk_answers.detect_intent(text) or local_provider.LocalAIProvider().detect_intent(text)


def _guardrail_text(language: str, check: rai.InputCheck | None) -> str:
    if language == "en":
        return rai.guardrail_response(language, check)
    lines = [i18n.translate("guardrail.no_advice", language), "",
             i18n.translate("guardrail.what_i_can", language)]
    if check and check.prediction_request:
        lines += ["", i18n.translate("guardrail.no_prediction", language)]
    lines += ["", talk_answers.ANSWERS[language]["guardrail_tail"]]
    return "\n".join(lines)


def _fallback_text(intent: str | None, language: str) -> str:
    if language == "en":
        if intent == "sip":
            return talk_answers.SIP_EN
        return local_provider._ANSWERS.get(intent or "", local_provider._UNKNOWN)
    bank = talk_answers.ANSWERS[language]
    return bank.get(intent or "", bank["unknown"])


_SCRIPT = {"hi": re.compile(r"[ऀ-ॿ]"), "ta": re.compile(r"[஀-௿]")}


def _script_matches(text: str, language: str) -> bool:
    """True when the question is written in the selected language's script.

    Otherwise (e.g. an English question while Hindi is selected) the panel uses
    the topic title in the selected language, so the page stays in one language.
    """
    if language in _SCRIPT:
        return bool(_SCRIPT[language].search(text))
    return not any(p.search(text) for p in _SCRIPT.values())


def _panel(question: str, reply: str, intent: str | None, language: str) -> dict[str, Any]:
    """Contextual explanation built from this turn - never a fixed topic."""
    q = " ".join(question.split())
    if (_QUESTION_START.search(q) or q.endswith("?")) and _script_matches(q, language):
        title = q[:1].upper() + q[1:]
        if len(title) > 90:
            title = title[:89].rstrip() + "…"
        elif not title.endswith(("?", "?", "।", ".")):
            title += "?"
    else:
        titles = talk_answers.TOPIC_TITLES[language]
        title = titles.get(intent or "", titles["unknown"])

    blocks = [b.strip() for b in reply.split("\n\n") if b.strip()]
    summary, points, closing = "", [], ""
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        bullets = [ln[2:].strip() for ln in lines if ln.startswith(("- ", "• ", "* "))]
        if bullets:
            points.extend(bullets)
        elif not summary:
            summary = " ".join(lines)
        else:
            closing = " ".join(lines)
    return {"title": title, "summary": summary, "points": points[:6], "closing": closing}


def _cache_key(check: rai.InputCheck, language: str) -> str | None:
    """Cache key for an impersonal question, or None when it must not be cached."""
    if check.sensitive_found or check.injection_found or not check.safe_to_send:
        return None
    question = " ".join(check.redacted_text.split()).lower()
    if not question or len(question) > _CACHE_MAX_CHARS or _PERSONAL.search(question):
        return None
    digest = hashlib.sha256(f"{language}\n{question}".encode("utf-8")).hexdigest()
    return f"talk:answer:{digest}"


def _cached_answer(key: str | None) -> dict[str, str] | None:
    if not key:
        return None
    hit = cache.get(key, stat="talk")
    if isinstance(hit, dict) and hit.get("reply"):
        return {"reply": str(hit["reply"]), "provider": str(hit.get("provider") or "cache")}
    return None


def _session(db, user: User, session_id: str | None, language: str, retain: bool) -> VoiceSession:
    if session_id:
        try:
            key = uuid.UUID(session_id)
        except ValueError:
            key = None
        if key is not None:
            found = db.execute(
                select(VoiceSession).where(VoiceSession.id == key, VoiceSession.user_id == user.id)
            ).scalar_one_or_none()
            if found is not None and found.ended_at is None:
                found.language = language
                return found
    session = VoiceSession(
        user_id=user.id, language=language, stt_provider="browser", tts_provider="browser",
        transcripts_retained=retain,
    )
    db.add(session)
    db.flush()
    return session


def respond(db, user: User, text: str, language: str, session_id: str | None = None) -> Turn:
    language = i18n.normalise(language)
    text = (text or "").strip()[:MAX_INPUT_CHARS]
    started = time.perf_counter()

    check = rai.check_input(text, language=language)
    intent = _intent(text)
    provider, offline, action, cached = "guardrail", False, "allow", False
    key: str | None = None

    if not check.safe_to_send:
        reply = check.direct_response if language == "en" else _CREDENTIAL_REPLY[language]
        action = "block"
    elif check.needs_guardrail_answer or intent in _GUARDRAIL_INTENTS:
        reply = _guardrail_text(language, check)
        action = "refuse"
    elif (hit := _cached_answer(key := _cache_key(check, language))) is not None:
        # Same impersonal question in the same language, answered by a real
        # model and passed the output guardrail within the last hour.
        reply, provider, cached = hit["reply"], hit["provider"], True
    else:
        completion = registry.complete(
            [
                Message("system", rai.system_prompt(language)),
                Message("user", rai.wrap_untrusted(check.redacted_text, label="spoken question")
                        if check.injection_found else check.redacted_text),
            ]
        )
        provider, offline = completion.provider, completion.is_fallback
        if completion.is_fallback:
            # Reviewed template in the selected language.
            reply = _fallback_text(intent, language)
        else:
            out = rai.check_output(completion.text, language=language)
            reply, action = out.text, out.action.lower()
            if key and action == "allow":
                cache.set(key, {"reply": reply, "provider": provider}, ttl=ANSWER_CACHE_TTL)

    retain = bool(user.privacy and user.privacy.store_voice_transcripts)
    session = _session(db, user, session_id, language, retain)
    if not session.title and session.transcripts_retained:
        session.title = check.redacted_text[:200]
    session.ai_provider = provider
    session.turn_count = (session.turn_count or 0) + 1
    latency = int((time.perf_counter() - started) * 1000)
    db.add(VoiceMessage(
        session_id=session.id, role="user", language=language,
        content=check.redacted_text if session.transcripts_retained else None,
        guardrail_notes=check.as_notes(),
    ))
    db.add(VoiceMessage(
        session_id=session.id, role="assistant", language=language,
        content=reply if session.transcripts_retained else None,
        guardrail_action=action, latency_ms=latency,
        # Provenance only (no text): feeds the admin "AI usage" aggregates.
        guardrail_notes={"provider": provider, "offline": offline, "cached": cached},
    ))

    return Turn(
        reply=reply,
        language=language,
        intent=intent,
        panel=_panel(check.redacted_text, reply, intent, language),
        provider=provider,
        offline=offline,
        guardrail=action,
        session_id=str(session.id),
        retained=session.transcripts_retained,
    )
