"""Deterministic, fully offline provider.

This is the floor of the stack: it never calls out, never fails, and never
invents facts. Instead of generating prose it assembles answers from a curated
template bank keyed by intent, and says plainly when it cannot help.

It exists so that every feature has an honest offline path - and so the demo
works on a machine with no model pulled.
"""
from __future__ import annotations

import hashlib
import math
import re
import time

from app.services.ai.base import AIProvider, Completion, EmbeddingResult, Message
from app.services.i18n import translate

# Intent -> canned, reviewed answer. Keys are matched as whole words.
_INTENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("advice_request", re.compile(
        r"\b(should i|shall i|must i|is it good to|worth)\b.*\b(buy|sell|hold|invest)\b"
        r"|\b(buy|sell|hold)\b.*\?",
        re.IGNORECASE)),
    ("price_prediction", re.compile(
        r"\b(will|would|is going to|gonna)\b.*\b(rise|fall|go up|go down|double|crash|"
        r"reach|hit)\b|\b(target price|price prediction|forecast)\b", re.IGNORECASE)),
    ("mutual_fund", re.compile(r"\bmutual fund(s)?\b|\bsip\b|\bnav\b", re.IGNORECASE)),
    ("guaranteed_return", re.compile(
        r"\bguarantee(d)?\b|\bassured\b|\brisk[- ]free\b|\bfixed return", re.IGNORECASE)),
    ("volatility", re.compile(r"\bvolatil|\bstandard deviation\b|\bfluctuat", re.IGNORECASE)),
    ("scam_check", re.compile(
        r"\bscam\b|\bfraud\b|\bfake\b|\bcheat(ed|ing)?\b|\bphish", re.IGNORECASE)),
    ("otp_request", re.compile(r"\botp\b|\bone[- ]time password\b|\bpin\b", re.IGNORECASE)),
    ("sebi_rights", re.compile(
        r"\bsebi\b|\binvestor right|\bcomplain|\bgrievance|\bscores\b", re.IGNORECASE)),
    ("diversification", re.compile(r"\bdiversif", re.IGNORECASE)),
    ("greeting", re.compile(r"^\s*(hi|hello|hey|namaste|vanakkam|good (morning|evening))",
                            re.IGNORECASE)),
]

_ANSWERS: dict[str, str] = {
    "advice_request": (
        "I cannot make a personalised buy, sell or hold decision for you, and I "
        "will not rank investments.\n\n"
        "What I can do instead:\n"
        "- explain what the information in front of you actually says\n"
        "- explain the relevant financial concepts in plain language\n"
        "- point out risks and what remains uncertain\n"
        "- list the questions worth asking and the facts worth verifying\n\n"
        "The decision stays yours. If you would like, tell me what you have been "
        "told and I will walk through it with you."
    ),
    "price_prediction": (
        "I do not predict prices or returns, and nobody can do so reliably.\n\n"
        "What is useful to understand:\n"
        "- past movement describes what already happened; it does not determine "
        "what happens next\n"
        "- short-term movement is particularly uncertain\n"
        "- anyone who states a future price with confidence is making a claim "
        "that cannot be verified\n\n"
        "I can explain how a metric like volatility is measured and what it does "
        "and does not tell you."
    ),
    "mutual_fund": (
        "A mutual fund pools money from many investors and a fund manager invests "
        "that pool according to a stated objective.\n\n"
        "Key ideas:\n"
        "- you own units of the fund, not the underlying shares directly\n"
        "- the unit value (NAV) moves with the value of what the fund holds\n"
        "- there are costs, usually expressed as an expense ratio\n"
        "- returns are not guaranteed and can be negative\n"
        "- a SIP is simply investing a fixed amount at regular intervals; it "
        "spreads out entry points but does not remove risk\n\n"
        "This is general education, not a recommendation about any specific fund."
    ),
    "guaranteed_return": (
        "Language promising guaranteed, assured or risk-free returns is a well-known "
        "warning signal in financial messages.\n\n"
        "Why it matters:\n"
        "- market-linked returns cannot be guaranteed by their nature\n"
        "- in India, only certain regulated products carry contractual guarantees, "
        "and they are modest and clearly documented\n"
        "- a high guaranteed figure combined with urgency is a common pattern in "
        "fraudulent solicitations\n\n"
        "What to verify:\n"
        "- who exactly is making the promise, and their registration\n"
        "- whether the promise appears in an official written document\n"
        "- what happens to your money if the promise is not met\n\n"
        "This signal alone does not establish fraud, but it does deserve checking."
    ),
    "volatility": (
        "Volatility describes how much a price has moved up and down over a period "
        "of time. It is a measure of variability, not of direction.\n\n"
        "At a high level it is calculated from the spread of past price changes "
        "around their average.\n\n"
        "What it can teach you:\n"
        "- prices can fluctuate significantly over short periods\n"
        "- a higher figure means larger past swings, in both directions\n"
        "- it says nothing about whether a price will rise or fall next\n\n"
        "Limitations: it is backward-looking, and a calm past period does not "
        "guarantee a calm future one."
    ),
    "scam_check": (
        "I can help you look at a message carefully.\n\n"
        "Patterns worth noticing:\n"
        "- promises of guaranteed or unusually high returns\n"
        "- pressure to act immediately, or a closing window\n"
        "- requests for an OTP, PIN, password or remote access to your device\n"
        "- claims of approval by a regulator that you cannot verify independently\n"
        "- payment to a personal account rather than a registered entity\n"
        "- links whose domain does not match the organisation named\n\n"
        "Use Check a Message to paste the text or upload a screenshot, and I will "
        "set out what was detected, why it matters, and what to verify."
    ),
    "otp_request": (
        "No legitimate bank, broker, regulator or government office will ever ask "
        "you for an OTP, PIN, password or card CVV - not by phone, message or email.\n\n"
        "An OTP exists to authorise one specific action. Sharing it lets someone "
        "else complete that action in your name.\n\n"
        "If you have already shared one: contact your bank through the number "
        "printed on your card or passbook, not a number from the message, and ask "
        "them to block and review recent transactions."
    ),
    "sebi_rights": (
        "As an investor in India you have a number of rights, including:\n"
        "- clear, written information about what you are being offered\n"
        "- dealing only with registered intermediaries, whose registration you can "
        "look up on the regulator's public website\n"
        "- a documented grievance process, and escalation to the regulator's "
        "complaints platform if a firm does not resolve your complaint\n"
        "- the right to decline, to take time, and to ask for everything in writing\n\n"
        "Verifying registration independently - typed into your browser yourself, "
        "not through a link you were sent - is one of the most useful habits."
    ),
    "diversification": (
        "Diversification means spreading money across different holdings so that "
        "no single outcome determines the whole result.\n\n"
        "The idea: different assets do not all move together, so combining them "
        "tends to reduce the variability of the total.\n\n"
        "What it does not do:\n"
        "- it does not remove risk\n"
        "- it does not protect against broad market declines, when most things "
        "fall together\n"
        "- it does not guarantee a positive result\n\n"
        "This is a concept, not a recommendation about how you should allocate."
    ),
    "greeting": (
        "Hello. I am NIRVAAN.\n\n"
        "I can explain financial information in plain language, look at a message "
        "you have received and point out warning signals, help you pause before "
        "acting, and walk through what is worth verifying.\n\n"
        "I do not tell you what to buy or sell - that decision stays with you.\n\n"
        "What would you like to start with?"
    ),
}

_UNKNOWN = (
    "I do not have a reliable answer for that while running fully offline.\n\n"
    "What I can still do right now:\n"
    "- explain common financial terms and concepts\n"
    "- check a message for known warning signals\n"
    "- walk you through the Pause & Reflect questions\n"
    "- show you saved lessons\n\n"
    "For anything that needs current information or a detailed explanation, "
    "please reconnect so the full assistant is available."
)


class LocalAIProvider(AIProvider):
    """Template-based provider. Always available, never generative."""

    name = "local"
    requires_network = False
    generative = False

    def health(self) -> tuple[bool, str]:
        return True, "Deterministic offline provider (no model required)"

    def detect_intent(self, text: str) -> str | None:
        for intent, pattern in _INTENT_PATTERNS:
            if pattern.search(text or ""):
                return intent
        return None

    def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int = 800,
        timeout: int | None = None,
    ) -> Completion:
        started = time.perf_counter()
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        intent = self.detect_intent(last_user)
        text = _ANSWERS.get(intent or "", _UNKNOWN)

        return Completion(
            text=text,
            provider=self.name,
            model="rule-template",
            is_fallback=True,
            latency_ms=int((time.perf_counter() - started) * 1000),
            usage={"intent": intent or "unknown"},
        )

    def refusal(self, language: str = "en") -> str:
        """The canonical guardrail refusal, translated."""
        return (
            translate("guardrail.no_advice", language)
            + " "
            + translate("guardrail.what_i_can", language)
        )

    # -- embeddings --------------------------------------------------------

    def embed(self, texts: list[str]) -> EmbeddingResult:
        """Deterministic hashing embedder.

        A bag-of-words hashing projection: not semantically strong, but stable
        and dependency-free, so RAG retrieval degrades to keyword-like matching
        instead of failing outright when no embedding model is available.
        """
        dim = 768
        vectors: list[list[float]] = []

        for text in texts:
            vector = [0.0] * dim
            tokens = re.findall(r"[\wऀ-ॿ஀-௿]+", (text or "").lower())
            for token in tokens:
                digest = hashlib.sha1(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % dim
                # Sign from a second byte range so collisions partially cancel.
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vector[index] += sign

            norm = math.sqrt(sum(v * v for v in vector))
            if norm:
                vector = [v / norm for v in vector]
            vectors.append(vector)

        return EmbeddingResult(
            vectors=vectors,
            provider=self.name,
            model="hashing-768",
            is_fallback=True,
            dim=dim,
        )
