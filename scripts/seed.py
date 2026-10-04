"""Create the schema and seed baseline data.

Idempotent: safe to re-run. Seeds roles, feature flags, safety rules, learning
content and market scenarios, plus optional demo accounts.

Run:  python scripts/seed.py
      python scripts/seed.py --demo-users
      python scripts/seed.py --reset        (drops and recreates: destructive)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timedelta, timezone  # noqa: E402

from sqlalchemy import func, select  # noqa: E402

import app.models  # noqa: F401,E402  registers every table
from app.db import Base, engine, session_scope  # noqa: E402
from app.models.analysis import (  # noqa: E402
    AnalysisSignal,
    BatchItem,
    BatchJob,
    MessageAnalysis,
    SafetyRule,
)
from app.models.enums import (  # noqa: E402
    AnalysisStatus,
    InputKind,
    JobStatus,
    PermissionScope,
    ReflectionLabel,
    Role,
    Severity,
    SignalType,
)
from app.models.family import FamilyPermission, FamilyRelationship  # noqa: E402
from app.models.learning import LearningContent, LearningProgress  # noqa: E402
from app.models.reflection import JournalEntry, ReflectionSession  # noqa: E402
from app.models.voice import VoiceMessage, VoiceSession  # noqa: E402
from app.models.market import MarketEducationalScenario  # noqa: E402
from app.models.system import FeatureFlag, Notification  # noqa: E402
from app.models.user import RoleRow  # noqa: E402
from app.services import auth as auth_service  # noqa: E402

# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

ROLES = [
    (Role.USER, "Standard account. Full access to their own data only."),
    (
        Role.FAMILY_ASSISTANT,
        "Trusted helper. Sees only scopes the account owner has explicitly shared.",
    ),
    (
        Role.ADMIN,
        "Operations. Manages content, safety rules, flags and health. "
        "No access to private user content.",
    ),
    (Role.DEMO_USER, "Read-mostly demo account with seeded sample data."),
]

# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------

FLAGS = [
    ("voice_assistant", "Voice conversation with speech-to-text and text-to-speech", True),
    ("ocr_upload", "Extract text from uploaded screenshots and PDFs", True),
    ("batch_analysis", "Analyse multiple files in one background job", True),
    ("market_education", "Educational market concepts and labelled simulations", True),
    ("family_mode", "Scoped sharing with a trusted family member", True),
    ("personal_memory", "Opt-in memory across conversations (off per user by default)", True),
    ("rag_retrieval", "Ground answers in the curated knowledge base", True),
    ("on_device_ai", "Prefer local classification when the device can handle it", False),
    ("low_bandwidth_mode", "Data-saver rendering path", True),
    ("offline_mode", "Service-worker offline support", True),
]

# ---------------------------------------------------------------------------
# Safety rules
#
# The deterministic half of the hybrid engine. Patterns are authored here, not
# user-supplied, and are applied to normalised text. Each carries the
# explanation and the verification hint the UI shows alongside the evidence.
# ---------------------------------------------------------------------------

SAFETY_RULES: list[dict] = [
    {
        "code": "GUARANTEED_RETURN_EN",
        "signal_type": SignalType.GUARANTEED_RETURN,
        "language": "en",
        "pattern": r"\b(guarantee[ds]?|assured|risk[\s-]?free|no[\s-]?risk|"
                   r"100%\s*safe|sure[\s-]?shot)\b.{0,40}\b(return|profit|income|"
                   r"gain|money)s?\b|\b(return|profit)s?\b.{0,20}\b(guarantee[ds]?|"
                   r"assured)\b",
        "severity": Severity.HIGH,
        "weight": 2.0,
        "explanation_en": "The message promises a guaranteed or risk-free return. "
                          "Market-linked returns cannot be guaranteed.",
        "explanation_hi": "संदेश निश्चित या जोखिम-मुक्त रिटर्न का वादा करता है। "
                          "बाज़ार से जुड़े रिटर्न की गारंटी संभव नहीं है।",
        "explanation_ta": "இந்தச் செய்தி உறுதியான அல்லது இடரில்லாத வருவாயை "
                          "உறுதியளிக்கிறது. சந்தை சார்ந்த வருவாய்க்கு உறுதி அளிக்க முடியாது.",
        "verify_hint_en": "Ask for the guarantee in writing, and check who is "
                          "legally bound by it and what happens if it is not met.",
    },
    {
        "code": "UNREALISTIC_RETURN_EN",
        "signal_type": SignalType.UNREALISTIC_RETURN,
        "language": "en",
        "pattern": r"\b([2-9]\d|\d{3,})\s*%\s*(?:return|profit|monthly|weekly|daily|"
                   r"per\s*month|per\s*week|p\.?m\.?)|\b(double|triple|3x|5x|10x)\b"
                   r".{0,30}\b(money|investment|amount|capital)\b",
        "severity": Severity.HIGH,
        "weight": 1.8,
        "explanation_en": "The return figure quoted is far above what regulated "
                          "products offer, especially over a short period.",
        "explanation_hi": "बताया गया रिटर्न विनियमित उत्पादों से बहुत अधिक है, "
                          "विशेष रूप से कम समय में।",
        "explanation_ta": "குறிப்பிடப்பட்ட வருவாய் ஒழுங்குமுறைப் பொருட்கள் "
                          "வழங்குவதை விட மிக அதிகம்.",
        "verify_hint_en": "Compare the figure with published returns of regulated "
                          "products over the same period.",
    },
    {
        "code": "URGENCY_EN",
        "signal_type": SignalType.URGENCY,
        "language": "en",
        "pattern": r"\b(urgent|immediately|right now|act now|hurry|quick(?:ly)?|"
                   r"don'?t delay|asap|before it'?s too late|last chance)\b",
        "severity": Severity.MEDIUM,
        "weight": 1.2,
        "explanation_en": "The message pushes for immediate action. Pressure to "
                          "act quickly reduces the chance you will verify it.",
        "explanation_hi": "संदेश तुरंत कार्रवाई के लिए दबाव डालता है। जल्दबाज़ी "
                          "सत्यापन की संभावना कम कर देती है।",
        "explanation_ta": "இந்தச் செய்தி உடனடியாகச் செயல்பட அழுத்தம் தருகிறது. "
                          "அவசரம் சரிபார்க்கும் வாய்ப்பைக் குறைக்கிறது.",
        "verify_hint_en": "Nothing legitimate collapses because you took a day to "
                          "check it. Take the time.",
    },
    {
        "code": "LIMITED_TIME_EN",
        "signal_type": SignalType.LIMITED_TIME_PRESSURE,
        "language": "en",
        "pattern": r"\b(limited (?:time|seats|slots|offer|period)|only \d+ (?:seats|"
                   r"slots|spots|left)|offer (?:ends|expires|closes)|closing (?:today|"
                   r"soon)|few seats)\b",
        "severity": Severity.MEDIUM,
        "weight": 1.3,
        "explanation_en": "A closing window is being used to limit how long you "
                          "have to think.",
        "explanation_hi": "सोचने का समय कम करने के लिए सीमित अवधि का दबाव "
                          "बनाया जा रहा है।",
        "explanation_ta": "யோசிக்கும் நேரத்தைக் குறைக்க கெடு அழுத்தம் "
                          "பயன்படுத்தப்படுகிறது.",
        "verify_hint_en": "Ask whether the same terms will be available next week. "
                          "A genuine offer usually will be.",
    },
    {
        "code": "FOMO_EN",
        "signal_type": SignalType.FOMO,
        "language": "en",
        "pattern": r"\b(don'?t miss (?:out|this)|missing out|everyone (?:is |'s )?"
                   r"(?:buying|investing|making)|opportunity of a lifetime|once[\s-]"
                   r"in[\s-]a[\s-]lifetime|you'?ll regret)\b",
        "severity": Severity.MEDIUM,
        "weight": 1.2,
        "explanation_en": "The message plays on fear of missing out rather than on "
                          "what the product actually is.",
        "explanation_hi": "संदेश उत्पाद की वास्तविकता के बजाय कुछ छूट जाने के डर "
                          "का उपयोग करता है।",
        "explanation_ta": "பொருளின் உண்மையைக் காட்டிலும் வாய்ப்பு தவறிவிடும் "
                          "என்ற பயத்தை இது பயன்படுத்துகிறது.",
        "verify_hint_en": "Ask what the product is and what the risks are. If that "
                          "is not answered plainly, the urgency is the product.",
    },
    {
        "code": "SOCIAL_PRESSURE_EN",
        "signal_type": SignalType.SOCIAL_PRESSURE,
        "language": "en",
        "pattern": r"\b(my (?:friend|cousin|uncle|neighbour|colleague) (?:made|earned|"
                   r"doubled)|thousands of (?:people|investors)|join \d+[,\d]* (?:members|"
                   r"investors)|everyone in (?:the |our )?group)\b",
        "severity": Severity.MEDIUM,
        "weight": 1.0,
        "explanation_en": "Other people's reported success is being offered as "
                          "evidence. It is not verifiable and may be fabricated.",
        "explanation_hi": "दूसरों की कथित सफलता को प्रमाण के रूप में दिखाया जा रहा "
                          "है। इसे सत्यापित नहीं किया जा सकता।",
        "explanation_ta": "பிறரின் வெற்றி ஆதாரமாகக் காட்டப்படுகிறது. அதைச் "
                          "சரிபார்க்க முடியாது.",
        "verify_hint_en": "Screenshots of profits are trivially faked. Ask for "
                          "documentation about the product instead.",
    },
    {
        "code": "LOSS_RECOVERY_EN",
        "signal_type": SignalType.LOSS_RECOVERY_PROMPT,
        "language": "en",
        "pattern": r"\b(recover (?:your )?(?:loss|losses|money|funds)|get (?:your )?"
                   r"money back|recoup|make up (?:for )?(?:your )?loss|compensation "
                   r"for (?:your )?loss)\b",
        "severity": Severity.HIGH,
        "weight": 1.9,
        "explanation_en": "An offer to recover a previous loss is a well-documented "
                          "second-stage pattern targeting people already affected.",
        "explanation_hi": "पिछला नुकसान वापस दिलाने का प्रस्ताव, पहले से प्रभावित "
                          "लोगों को निशाना बनाने वाला एक ज्ञात दूसरा चरण है।",
        "explanation_ta": "ஏற்கனவே பாதிக்கப்பட்டவர்களை இலக்காகக் கொண்ட "
                          "அறியப்பட்ட இரண்டாம் கட்ட முறை இது.",
        "verify_hint_en": "Legitimate recovery happens through your bank or the "
                          "regulator's complaints process, never for an upfront fee.",
    },
    {
        "code": "OTP_REQUEST_EN",
        "signal_type": SignalType.OTP_REQUEST,
        "language": "en",
        "pattern": r"\b(share|send|tell|give|forward|provide)\b.{0,30}\b(otp|one[\s-]?"
                   r"time[\s-]?password|verification code|pin)\b|\botp\b.{0,20}"
                   r"\b(share|send|tell|forward)\b",
        "severity": Severity.HIGH,
        "weight": 3.0,
        "explanation_en": "The message asks for an OTP or PIN. No legitimate "
                          "organisation ever does this.",
        "explanation_hi": "संदेश OTP या PIN मांगता है। कोई वैध संस्था ऐसा कभी "
                          "नहीं करती।",
        "explanation_ta": "இந்தச் செய்தி OTP அல்லது PIN கேட்கிறது. எந்த முறையான "
                          "நிறுவனமும் இதைக் கேட்காது.",
        "verify_hint_en": "Do not share it. An OTP authorises one specific "
                          "transaction in your name.",
    },
    {
        "code": "CREDENTIAL_REQUEST_EN",
        "signal_type": SignalType.CREDENTIAL_REQUEST,
        "language": "en",
        "pattern": r"\b(share|send|tell|enter|confirm|verify|update)\b.{0,30}"
                   r"\b(password|cvv|card number|net\s?banking|login|credentials|"
                   r"user\s?id)\b",
        "severity": Severity.HIGH,
        "weight": 3.0,
        "explanation_en": "The message asks for login details or card information.",
        "explanation_hi": "संदेश लॉगिन विवरण या कार्ड जानकारी मांगता है।",
        "explanation_ta": "இந்தச் செய்தி உள்நுழைவு விவரங்கள் அல்லது அட்டைத் "
                          "தகவலைக் கேட்கிறது.",
        "verify_hint_en": "Never enter these from a link. Open the app or type the "
                          "website address yourself.",
    },
    {
        "code": "REMOTE_ACCESS_EN",
        "signal_type": SignalType.REMOTE_ACCESS_REQUEST,
        "language": "en",
        "pattern": r"\b(anydesk|teamviewer|quick\s?support|screen\s?share|remote "
                   r"access|install (?:this |the )?app|download (?:this |the )?apk)\b",
        "severity": Severity.HIGH,
        "weight": 2.8,
        "explanation_en": "The message asks you to install software or grant remote "
                          "access to your device.",
        "explanation_hi": "संदेश आपसे सॉफ़्टवेयर इंस्टॉल करने या डिवाइस तक रिमोट "
                          "एक्सेस देने के लिए कहता है।",
        "explanation_ta": "உங்கள் சாதனத்தில் மென்பொருளை நிறுவ அல்லது தொலைநிலை "
                          "அணுகலை வழங்கக் கேட்கிறது.",
        "verify_hint_en": "Remote access lets someone operate your banking apps. No "
                          "support process legitimately requires it.",
    },
    {
        "code": "PAYMENT_REQUEST_EN",
        "signal_type": SignalType.PAYMENT_REQUEST,
        "language": "en",
        "pattern": r"\b(transfer|deposit|pay|send money|upi|gpay|phonepe|paytm|"
                   r"scan (?:this )?qr)\b.{0,40}\b(now|today|immediately|account|"
                   r"number)\b|\b(processing|registration|activation|release)\s+fee\b",
        "severity": Severity.HIGH,
        "weight": 1.7,
        "explanation_en": "The message asks for a payment, often an upfront fee "
                          "before anything is delivered.",
        "explanation_hi": "संदेश भुगतान मांगता है, अक्सर कुछ मिलने से पहले "
                          "अग्रिम शुल्क।",
        "explanation_ta": "இந்தச் செய்தி பணம் கேட்கிறது, பெரும்பாலும் எதுவும் "
                          "கிடைக்கும் முன் முன்பணமாக.",
        "verify_hint_en": "Check whether the account belongs to a registered entity "
                          "or an individual. Personal accounts are a strong signal.",
    },
    {
        "code": "FAKE_AUTHORITY_EN",
        "signal_type": SignalType.UNVERIFIED_REGULATORY_CLAIM,
        "language": "en",
        "pattern": r"\b(sebi|rbi|irdai|nse|bse|government)\b.{0,40}\b(approved|"
                   r"registered|certified|authorised|backed|guaranteed)\b"
                   r"|\b(approved|registered|certified)\s+by\s+(?:sebi|rbi|irdai|"
                   r"government)\b",
        "severity": Severity.HIGH,
        "weight": 1.8,
        "explanation_en": "A regulator's name is used as proof of legitimacy. "
                          "Regulators register intermediaries; they do not endorse "
                          "or guarantee returns.",
        "explanation_hi": "नियामक के नाम को वैधता के प्रमाण के रूप में इस्तेमाल किया "
                          "गया है। नियामक रिटर्न की गारंटी नहीं देते।",
        "explanation_ta": "ஒழுங்குமுறை அமைப்பின் பெயர் சட்டப்பூர்வத்தன்மைக்கான "
                          "ஆதாரமாகப் பயன்படுத்தப்படுகிறது. அவர்கள் வருவாய்க்கு "
                          "உறுதி அளிப்பதில்லை.",
        "verify_hint_en": "Look up the registration number yourself on the "
                          "regulator's official website, typed in by you.",
    },
    {
        "code": "IMPERSONATION_EN",
        "signal_type": SignalType.IMPERSONATION,
        "language": "en",
        "pattern": r"\b(?:i am|this is|calling from|on behalf of)\b.{0,30}"
                   r"\b(bank|manager|officer|executive|police|cyber cell|income tax|"
                   r"customs|court)\b|\b(?:your )?(?:account|card) (?:will be |has been )"
                   r"?(?:blocked|suspended|frozen|closed)\b",
        "severity": Severity.HIGH,
        "weight": 1.9,
        "explanation_en": "The sender claims to be an official, often combined with "
                          "a threat about your account.",
        "explanation_hi": "भेजने वाला स्वयं को अधिकारी बताता है, अक्सर आपके खाते "
                          "के बारे में धमकी के साथ।",
        "explanation_ta": "அனுப்புநர் தன்னை அதிகாரி எனக் கூறுகிறார், "
                          "பெரும்பாலும் கணக்கு பற்றிய மிரட்டலுடன்.",
        "verify_hint_en": "Hang up and call back on the number printed on your card "
                          "or passbook - never a number from the message.",
    },
    {
        "code": "MISLEADING_TESTIMONIAL_EN",
        "signal_type": SignalType.MISLEADING_TESTIMONIAL,
        "language": "en",
        "pattern": r"\b(?:screenshot|proof|profit)\b.{0,30}\b(?:attached|below|see)\b"
                   r"|\bi (?:made|earned|withdrew)\b.{0,20}(?:rs\.?|₹|inr)\s?[\d,]+"
                   r"|\bpayment proof\b",
        "severity": Severity.LOW,
        "weight": 0.8,
        "explanation_en": "Claimed profits or payment screenshots are offered as "
                          "evidence. These are easily fabricated.",
        "explanation_hi": "कथित लाभ या भुगतान स्क्रीनशॉट प्रमाण के रूप में दिए गए "
                          "हैं। इन्हें आसानी से बनाया जा सकता है।",
        "explanation_ta": "கூறப்படும் லாபம் அல்லது பணப் படங்கள் ஆதாரமாகத் "
                          "தரப்படுகின்றன. இவை எளிதில் போலியாக உருவாக்கப்படும்.",
        "verify_hint_en": "Ask for the product documentation and registration "
                          "instead of other people's results.",
    },
    # --- Hindi-language patterns -----------------------------------------
    {
        "code": "GUARANTEED_RETURN_HI",
        "signal_type": SignalType.GUARANTEED_RETURN,
        "language": "hi",
        "pattern": r"(गारंटी|गारंटीड|निश्चित|पक्का|जोखिम\s*मुक्त).{0,30}"
                   r"(रिटर्न|मुनाफ़ा|मुनाफा|लाभ|कमाई)",
        "severity": Severity.HIGH,
        "weight": 2.0,
        "explanation_en": "The message promises a guaranteed return (in Hindi).",
        "explanation_hi": "संदेश निश्चित रिटर्न का वादा करता है। बाज़ार से जुड़े "
                          "रिटर्न की गारंटी संभव नहीं है।",
        "explanation_ta": "இந்தச் செய்தி உறுதியான வருவாயை உறுதியளிக்கிறது.",
        "verify_hint_en": "Ask for the guarantee in writing and check who is bound by it.",
    },
    {
        "code": "URGENCY_HI",
        "signal_type": SignalType.URGENCY,
        "language": "hi",
        "pattern": r"(तुरंत|अभी|जल्दी|शीघ्र|देर\s*न\s*करें|आखिरी\s*मौका|अंतिम\s*अवसर)",
        "severity": Severity.MEDIUM,
        "weight": 1.2,
        "explanation_en": "The message pushes for immediate action (in Hindi).",
        "explanation_hi": "संदेश तुरंत कार्रवाई के लिए दबाव डालता है।",
        "explanation_ta": "இந்தச் செய்தி உடனடியாகச் செயல்பட அழுத்தம் தருகிறது.",
        "verify_hint_en": "Take a day to verify. Nothing legitimate expires that fast.",
    },
    {
        "code": "OTP_REQUEST_HI",
        "signal_type": SignalType.OTP_REQUEST,
        "language": "hi",
        "pattern": r"(ओटीपी|ओ\.?टी\.?पी|पिन).{0,30}(बताएं|भेजें|शेयर|साझा|दें)"
                   r"|(बताएं|भेजें|शेयर|साझा).{0,20}(ओटीपी|पिन)",
        "severity": Severity.HIGH,
        "weight": 3.0,
        "explanation_en": "The message asks for an OTP or PIN (in Hindi).",
        "explanation_hi": "संदेश OTP या PIN मांगता है। कोई वैध संस्था ऐसा नहीं करती।",
        "explanation_ta": "இந்தச் செய்தி OTP அல்லது PIN கேட்கிறது.",
        "verify_hint_en": "Do not share it with anyone, for any reason.",
    },
    # --- Tamil-language patterns -----------------------------------------
    {
        "code": "GUARANTEED_RETURN_TA",
        "signal_type": SignalType.GUARANTEED_RETURN,
        "language": "ta",
        "pattern": r"(உறுதி|உத்தரவாத|நிச்சயம்|இடரில்லா).{0,30}"
                   r"(வருவாய்|லாபம்|வருமானம்)",
        "severity": Severity.HIGH,
        "weight": 2.0,
        "explanation_en": "The message promises a guaranteed return (in Tamil).",
        "explanation_hi": "संदेश निश्चित रिटर्न का वादा करता है।",
        "explanation_ta": "இந்தச் செய்தி உறுதியான வருவாயை உறுதியளிக்கிறது. "
                          "சந்தை சார்ந்த வருவாய்க்கு உறுதி அளிக்க முடியாது.",
        "verify_hint_en": "Ask for the guarantee in writing and check who is bound by it.",
    },
    {
        "code": "URGENCY_TA",
        "signal_type": SignalType.URGENCY,
        "language": "ta",
        "pattern": r"(உடனே|உடனடியாக|விரைவாக|தாமதிக்க\s*வேண்டாம்|கடைசி\s*வாய்ப்பு)",
        "severity": Severity.MEDIUM,
        "weight": 1.2,
        "explanation_en": "The message pushes for immediate action (in Tamil).",
        "explanation_hi": "संदेश तुरंत कार्रवाई के लिए दबाव डालता है।",
        "explanation_ta": "இந்தச் செய்தி உடனடியாகச் செயல்பட அழுத்தம் தருகிறது.",
        "verify_hint_en": "Take a day to verify. Nothing legitimate expires that fast.",
    },
    {
        "code": "OTP_REQUEST_TA",
        "signal_type": SignalType.OTP_REQUEST,
        "language": "ta",
        "pattern": r"(ஓடிபி|ஓ\.?டி\.?பி|பின்\s*எண்).{0,30}"
                   r"(சொல்|அனுப்ப|பகிர|கொடு)",
        "severity": Severity.HIGH,
        "weight": 3.0,
        "explanation_en": "The message asks for an OTP or PIN (in Tamil).",
        "explanation_hi": "संदेश OTP या PIN मांगता है।",
        "explanation_ta": "இந்தச் செய்தி OTP அல்லது PIN கேட்கிறது. எந்த முறையான "
                          "நிறுவனமும் இதைக் கேட்காது.",
        "verify_hint_en": "Do not share it with anyone, for any reason.",
    },
]

# ---------------------------------------------------------------------------
# Learning content
# ---------------------------------------------------------------------------

LEARNING: list[dict] = [
    {
        "slug": "what-is-a-mutual-fund",
        "category": "mutual-funds",
        "title": "What is a mutual fund?",
        "icon": "pie_chart",
        "reading_minutes": 4,
        "summary": "A pooled investment managed to a stated objective - and what "
                   "that means for your money.",
        "body": "A mutual fund collects money from many investors and invests that "
                "pool according to an objective written down in advance.\n\n"
                "You own units of the fund rather than the underlying shares or "
                "bonds directly. The value of a unit, called the NAV, moves with "
                "the value of what the fund holds.\n\n"
                "Costs matter. The expense ratio is deducted from the fund's assets "
                "every year, whether the fund gains or loses.\n\n"
                "Returns are not guaranteed and can be negative. A fund's past "
                "performance describes what already happened; it does not "
                "determine what happens next.",
        "simple_body": "Many people put money together. A manager invests it. You "
                       "get units. If the investments gain value, your units are "
                       "worth more. If they lose value, your units are worth less. "
                       "Nobody can promise you a profit.",
        "source": "NIRVAAN investor education",
    },
    {
        "slug": "understanding-sip",
        "category": "mutual-funds",
        "title": "What a SIP does, and does not, do",
        "icon": "event_repeat",
        "reading_minutes": 3,
        "summary": "Investing a fixed amount regularly spreads out your entry "
                   "points. It does not remove risk.",
        "body": "A Systematic Investment Plan means investing a fixed amount at "
                "regular intervals rather than all at once.\n\n"
                "What it does: it spreads your purchases across different price "
                "levels, so a single unlucky entry date matters less. It also "
                "makes investing a habit rather than a decision you re-make each "
                "month.\n\n"
                "What it does not do: it does not guarantee a profit, it does not "
                "protect you if the whole market falls, and it does not make a "
                "poorly chosen fund a good one.\n\n"
                "Anyone describing a SIP as risk-free is describing it wrongly.",
        "source": "NIRVAAN investor education",
    },
    {
        "slug": "guaranteed-return-warning",
        "category": "scams",
        "title": "Why 'guaranteed returns' is a warning signal",
        "icon": "warning",
        "reading_minutes": 3,
        "summary": "What guarantees legitimately exist, and why a high guaranteed "
                   "figure is one of the strongest signals there is.",
        "body": "Market-linked returns cannot be guaranteed. The value of shares, "
                "bonds and funds changes, and nobody controls that.\n\n"
                "Some regulated products do carry contractual commitments - certain "
                "deposits and insurance products, for example. These are modest, "
                "clearly documented, and backed by an identifiable institution.\n\n"
                "So when a message promises a high guaranteed return, there are "
                "three questions worth asking:\n\n"
                "1. Who exactly is legally bound by this promise, and are they "
                "registered?\n"
                "2. Where is the promise written down?\n"
                "3. What happens to my money if the promise is not met?\n\n"
                "A guaranteed-return claim on its own does not establish fraud. It "
                "does mean the claim deserves checking before anything else.",
        "source": "NIRVAAN fraud awareness",
    },
    {
        "slug": "never-share-otp",
        "category": "digital-safety",
        "title": "Never share an OTP, PIN or password",
        "icon": "password",
        "reading_minutes": 2,
        "summary": "What an OTP actually authorises, and what to do if you have "
                   "already shared one.",
        "body": "An OTP exists to authorise one specific action - a payment, a "
                "login, a change of details. Sharing it lets someone else complete "
                "that action in your name.\n\n"
                "No bank, broker, regulator, government office or delivery company "
                "will ever ask you for an OTP, PIN, password or card CVV. Not by "
                "phone, not by message, not by email. There is no exception, and no "
                "verification process that needs it.\n\n"
                "If you have already shared one:\n\n"
                "1. Call your bank on the number printed on your card or passbook.\n"
                "2. Ask them to block the card or account and review recent "
                "transactions.\n"
                "3. Report it at cybercrime.gov.in or on 1930. Report early.\n"
                "4. Keep the messages and transaction references.\n\n"
                "Being targeted is not your fault. Acting quickly matters more than "
                "feeling embarrassed.",
        "simple_body": "An OTP is a key. If you give someone the key, they can take "
                       "your money. Nobody honest will ever ask you for it. If you "
                       "already gave it, call your bank now using the number on your "
                       "card, and report it on 1930.",
        "source": "NIRVAAN digital safety",
    },
    {
        "slug": "investor-rights-india",
        "category": "investor-rights",
        "title": "Your rights as an investor",
        "icon": "gavel",
        "reading_minutes": 4,
        "summary": "What you are entitled to ask for, and the escalation path when "
                   "a firm does not resolve your complaint.",
        "body": "As an investor you are entitled to:\n\n"
                "- Clear, written information about what you are being offered, "
                "including costs and risks.\n"
                "- Deal only with registered intermediaries. Registration is public "
                "and you can look it up yourself.\n"
                "- A documented grievance process, with defined timelines.\n"
                "- Escalation to the regulator's complaints platform if a firm does "
                "not resolve your complaint.\n"
                "- Say no, take your time, and ask for everything in writing.\n\n"
                "The most useful habit is verifying registration independently: "
                "open the regulator's official website by typing the address "
                "yourself, and search for the firm or person. Never use a link you "
                "were sent, however official it looks.",
        "source": "NIRVAAN investor rights",
    },
    {
        "slug": "what-is-volatility",
        "category": "risk-volatility",
        "title": "What volatility means",
        "icon": "show_chart",
        "reading_minutes": 3,
        "summary": "A measure of how much a price has moved - not of which "
                   "direction it will move next.",
        "body": "Volatility describes how much a price has moved up and down over a "
                "period. It measures variability, not direction.\n\n"
                "At a high level, it is calculated from how widely past price "
                "changes were spread around their average. A larger spread means a "
                "higher figure.\n\n"
                "What it can teach you:\n\n"
                "- Prices can fluctuate significantly over short periods.\n"
                "- A higher figure means larger past swings, in both directions.\n"
                "- Two investments with similar average returns can feel completely "
                "different to hold.\n\n"
                "Limitations: it is entirely backward-looking. A calm past period "
                "does not guarantee a calm future one, and volatility says nothing "
                "about whether a price will rise or fall.",
        "source": "NIRVAAN market concepts",
    },
    {
        "slug": "diversification-basics",
        "category": "market-concepts",
        "title": "What diversification does",
        "icon": "scatter_plot",
        "reading_minutes": 3,
        "summary": "Spreading money across holdings reduces variability. It does "
                   "not remove risk.",
        "body": "Diversification means spreading money across different holdings so "
                "that no single outcome determines the whole result.\n\n"
                "The underlying idea is that different assets do not all move "
                "together. Combining them tends to reduce the variability of the "
                "total compared with holding just one.\n\n"
                "What it does not do:\n\n"
                "- It does not remove risk.\n"
                "- It does not protect against broad market declines, when most "
                "things fall at once.\n"
                "- It does not guarantee a positive result.\n\n"
                "Diversification is a concept for understanding risk, not a "
                "recommendation about how anyone should allocate their money.",
        "source": "NIRVAAN market concepts",
    },
    {
        "slug": "budgeting-first-steps",
        "category": "budgeting",
        "title": "First steps in budgeting",
        "icon": "savings",
        "reading_minutes": 3,
        "summary": "Knowing what comes in, what goes out, and what you would do if "
                   "income stopped for a month.",
        "body": "Budgeting starts with observation rather than restriction. For one "
                "month, write down what comes in and what goes out. Most people are "
                "surprised by at least one category.\n\n"
                "Three questions that tend to matter more than any budgeting method:\n\n"
                "1. What are my fixed commitments each month - rent, EMIs, fees?\n"
                "2. What would I do if my income stopped for one month?\n"
                "3. What am I currently paying interest on?\n\n"
                "High-interest debt usually costs more than most investments "
                "reasonably return, which is why it generally gets attention first.\n\n"
                "An emergency buffer in something you can access quickly is what "
                "stops an unexpected expense from becoming a high-interest loan.",
        "source": "NIRVAAN financial literacy",
    },
    {
        "slug": "recognising-pressure-tactics",
        "category": "scams",
        "title": "Recognising pressure tactics",
        "icon": "running_with_errors",
        "reading_minutes": 3,
        "summary": "The patterns used to stop you from verifying - urgency, "
                   "scarcity, authority and social proof.",
        "body": "Most financial fraud does not rely on a clever product. It relies "
                "on stopping you from checking.\n\n"
                "Four patterns do most of the work:\n\n"
                "Urgency - act now, today only, before it is too late. The purpose "
                "is to shorten the time you have to think.\n\n"
                "Scarcity - limited seats, only three slots left. The purpose is to "
                "make hesitation feel like loss.\n\n"
                "Authority - a regulator's name, an official title, a uniform in a "
                "profile photo. The purpose is to borrow trust that has not been "
                "earned.\n\n"
                "Social proof - screenshots of other people's profits, a group full "
                "of enthusiastic members. The purpose is to make verification feel "
                "unnecessary.\n\n"
                "The counter to all four is the same: slow down, and verify "
                "independently. Nothing legitimate is damaged by you taking a day.",
        "source": "NIRVAAN fraud awareness",
    },
    {
        "slug": "basics-risk-and-return",
        "category": "basics",
        "title": "Risk and return, honestly",
        "icon": "balance",
        "reading_minutes": 3,
        "summary": "Why higher potential return always comes with higher "
                   "uncertainty - and what that means in practice.",
        "body": "Across investments, a higher potential return comes with higher "
                "uncertainty about the outcome. This is not a rule someone imposed; "
                "it follows from the fact that people have to be compensated for "
                "accepting a less predictable result.\n\n"
                "The practical consequence is simple: if something offers a return "
                "well above what safe, regulated options give, it is carrying more "
                "risk somewhere - even if the person offering it does not say so.\n\n"
                "An offer of high return with low or no risk is describing something "
                "that does not exist. That combination is itself the warning signal.\n\n"
                "Understanding this does not tell you what to invest in. It tells "
                "you which claims to be sceptical about.",
        "source": "NIRVAAN financial literacy",
    },
]

# ---------------------------------------------------------------------------
# Market education scenarios
# ---------------------------------------------------------------------------


def _synthetic_series(seed: int, points: int = 120, start: float = 100.0,
                      drift: float = 0.0002, vol: float = 0.012) -> list[dict]:
    """Deterministic pseudo-random walk for teaching charts.

    Seeded so the chart is identical on every run and on every machine. It is
    explicitly synthetic, and every scenario built on it is labelled as such.
    """
    import math
    import random

    rng = random.Random(seed)
    value = start
    series: list[dict] = []
    for day in range(points):
        shock = rng.gauss(0, 1)
        value *= math.exp(drift - 0.5 * vol * vol + vol * shock)
        series.append({"t": day, "v": round(value, 2)})
    return series


MARKET_SCENARIOS: list[dict] = [
    {
        "slug": "volatility-explained",
        "concept": "volatility",
        "title": "What does volatility mean?",
        "what_it_means": "Volatility describes how much a price has historically "
                         "changed over a period of time. It measures variability, "
                         "not direction.",
        "how_it_is_calculated": "At a high level, past price changes are compared "
                                "with their own average, and the typical size of "
                                "that difference is summarised as a single figure. "
                                "A wider spread of changes gives a higher number.",
        "why_people_care": "It gives a sense of how much a holding's value may move "
                           "around in the short term, which affects how it feels to "
                           "hold and whether it suits money you may need soon.",
        "limitations": "It is entirely backward-looking. A calm past period does not "
                       "guarantee a calm future one, and it says nothing about "
                       "whether a price will rise or fall.",
        "what_this_teaches": [
            "Prices can fluctuate significantly.",
            "Short-term movement is uncertain.",
            "Historical movement does not guarantee future results.",
        ],
        "chart_kind": "line",
        "chart_data": {
            "series": [
                {"name": "Lower volatility", "points": _synthetic_series(11, vol=0.006)},
                {"name": "Higher volatility", "points": _synthetic_series(12, vol=0.028)},
            ],
            "y_label": "Indexed value (starts at 100)",
            "x_label": "Trading days",
        },
    },
    {
        "slug": "drawdown-explained",
        "concept": "drawdown",
        "title": "What is a drawdown?",
        "what_it_means": "A drawdown is the fall from a previous peak to a later "
                         "low. The maximum drawdown is the largest such fall over "
                         "the period being examined.",
        "how_it_is_calculated": "The highest value reached so far is tracked, and "
                                "each later value is compared with it. The largest "
                                "percentage gap is the maximum drawdown.",
        "why_people_care": "It describes the worst decline someone holding through "
                           "that period would have experienced - which is often "
                           "what people actually find difficult, rather than the "
                           "average return.",
        "limitations": "It describes one historical path. A future decline could be "
                       "larger, smaller or longer, and the figure says nothing "
                       "about recovery time.",
        "what_this_teaches": [
            "Declines are part of how markets have historically behaved.",
            "An average return hides the path taken to get there.",
            "Past declines do not bound future ones.",
        ],
        "chart_kind": "area",
        "chart_data": {
            "series": [
                {"name": "Indexed value", "points": _synthetic_series(21, vol=0.02, drift=0.0004)}
            ],
            "y_label": "Indexed value",
            "x_label": "Trading days",
        },
    },
    {
        "slug": "market-cycles-explained",
        "concept": "market-cycles",
        "title": "What are market cycles?",
        "what_it_means": "Markets have historically moved through extended periods "
                         "of rising and falling prices rather than changing at a "
                         "steady rate.",
        "how_it_is_calculated": "Cycles are described after the fact, by looking "
                                "back at price history and identifying sustained "
                                "periods of rise and fall. There is no formula that "
                                "identifies them in advance.",
        "why_people_care": "Knowing that extended rises and falls have both occurred "
                           "historically can make a current period feel less like "
                           "either a guarantee or a catastrophe.",
        "limitations": "Cycles are only clear in hindsight. They have no fixed "
                       "length or depth, and recognising one in the past does not "
                       "mean the next can be timed.",
        "what_this_teaches": [
            "Both extended rises and extended falls have happened before.",
            "Cycles are identified in hindsight, not predicted.",
            "No pattern in past cycles determines the next one.",
        ],
        "chart_kind": "line",
        "chart_data": {
            "series": [
                {"name": "Long-run indexed value",
                 "points": _synthetic_series(31, points=240, vol=0.014, drift=0.0005)}
            ],
            "y_label": "Indexed value",
            "x_label": "Trading days",
        },
    },
    {
        "slug": "volatility-portfolio-simulation",
        "concept": "volatility",
        "title": "How volatility can affect a hypothetical portfolio",
        "is_simulation": True,
        "what_it_means": "This is a simulation, not a forecast. It shows how two "
                         "hypothetical portfolios with the same average drift but "
                         "different volatility can end up on very different paths.",
        "how_it_is_calculated": "Both paths are generated from the same synthetic "
                                "model with identical average drift. Only the "
                                "volatility parameter differs. No real instrument "
                                "is represented.",
        "why_people_care": "It illustrates why two things described by the same "
                           "average return can be experienced very differently.",
        "limitations": "These are generated numbers. They are not a prediction, not "
                       "a recommendation about allocation, and not based on any "
                       "actual security.",
        "what_this_teaches": [
            "Identical average drift can produce very different paths.",
            "Higher volatility widens the range of outcomes in both directions.",
            "A simulation shows possibilities, never a forecast.",
        ],
        "chart_kind": "line",
        "chart_data": {
            "series": [
                {"name": "Lower volatility path",
                 "points": _synthetic_series(41, vol=0.008, drift=0.0004)},
                {"name": "Higher volatility path",
                 "points": _synthetic_series(42, vol=0.032, drift=0.0004)},
            ],
            "y_label": "Hypothetical value (starts at 100)",
            "x_label": "Trading days",
        },
    },
]


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


def seed_roles(db) -> int:
    created = 0
    for role, description in ROLES:
        row = db.execute(
            select(RoleRow).where(RoleRow.name == role.value)
        ).scalar_one_or_none()
        if row is None:
            db.add(RoleRow(name=role.value, description=description))
            created += 1
        else:
            row.description = description
    return created


def seed_flags(db) -> int:
    created = 0
    for key, description, enabled in FLAGS:
        row = db.execute(
            select(FeatureFlag).where(FeatureFlag.key == key)
        ).scalar_one_or_none()
        if row is None:
            db.add(
                FeatureFlag(key=key, description=description, enabled=enabled)
            )
            created += 1
        else:
            # Keep descriptions fresh but never override an admin's toggle.
            row.description = description
    return created


def seed_safety_rules(db) -> int:
    created = 0
    for spec in SAFETY_RULES:
        row = db.execute(
            select(SafetyRule).where(SafetyRule.code == spec["code"])
        ).scalar_one_or_none()
        values = {
            "signal_type": str(spec["signal_type"]),
            "language": spec["language"],
            "pattern": spec["pattern"],
            "severity": str(spec["severity"]),
            "weight": spec["weight"],
            "explanation_en": spec["explanation_en"],
            "explanation_hi": spec.get("explanation_hi", ""),
            "explanation_ta": spec.get("explanation_ta", ""),
            "verify_hint_en": spec.get("verify_hint_en", ""),
        }
        if row is None:
            db.add(SafetyRule(code=spec["code"], enabled=True, **values))
            created += 1
        else:
            for key, value in values.items():
                setattr(row, key, value)
    return created


def seed_learning(db) -> int:
    created = 0
    for index, spec in enumerate(LEARNING):
        row = db.execute(
            select(LearningContent).where(LearningContent.slug == spec["slug"])
        ).scalar_one_or_none()
        values = {
            "category": spec["category"],
            "language": spec.get("language", "en"),
            "title": spec["title"],
            "summary": spec["summary"],
            "body": spec["body"],
            "simple_body": spec.get("simple_body"),
            "icon": spec.get("icon", "school"),
            "reading_minutes": spec.get("reading_minutes", 3),
            "source": spec.get("source", "NIRVAAN"),
            "order_index": index,
            "offline_available": True,
            "published": True,
        }
        if row is None:
            db.add(LearningContent(slug=spec["slug"], **values))
            created += 1
        else:
            for key, value in values.items():
                setattr(row, key, value)
    return created


def seed_market(db) -> int:
    created = 0
    for index, spec in enumerate(MARKET_SCENARIOS):
        row = db.execute(
            select(MarketEducationalScenario).where(
                MarketEducationalScenario.slug == spec["slug"]
            )
        ).scalar_one_or_none()
        values = {
            "concept": spec["concept"],
            "language": spec.get("language", "en"),
            "title": spec["title"],
            "what_it_means": spec["what_it_means"],
            "how_it_is_calculated": spec["how_it_is_calculated"],
            "why_people_care": spec["why_people_care"],
            "limitations": spec["limitations"],
            "what_this_teaches": {"points": spec["what_this_teaches"]},
            "chart_data": spec["chart_data"],
            "chart_kind": spec.get("chart_kind", "line"),
            "is_simulation": spec.get("is_simulation", False),
            # Every seeded series is generated, never presented as live data.
            "is_synthetic": True,
            "order_index": index,
            "published": True,
        }
        if row is None:
            db.add(MarketEducationalScenario(slug=spec["slug"], **values))
            created += 1
        else:
            for key, value in values.items():
                setattr(row, key, value)
    return created


DEMO_USERS = [
    ("Priya Sharma", "priya@nirvaan.local", "NirvaanDemo2026", "en", Role.USER),
    ("Arun Kumar", "arun@nirvaan.local", "NirvaanDemo2026", "ta", Role.FAMILY_ASSISTANT),
    # Password deliberately avoids the words "admin"/"nirvaan": the
    # strength check rejects passwords containing the name or email.
    ("Ops Console", "admin@nirvaan.local", "QuietLotus7Harbour", "en", Role.ADMIN),
]


def seed_demo_users(db) -> int:
    created = 0
    for name, email, password, language, role in DEMO_USERS:
        if auth_service.get_user_by_email(db, email) is not None:
            continue
        result = auth_service.register(
            db,
            full_name=name,
            email=email,
            password=password,
            language=language,
            role=role,
        )
        if result.ok and result.user is not None:
            # Demo accounts skip the mail round-trip.
            result.user.email_verified_at = datetime.now(timezone.utc)
            created += 1
        else:
            print(f"  ! could not create {email}: {result.error_text}")
    return created


# Demo profile genders. Accounts not listed (admin) keep None.
DEMO_GENDERS = {
    "priya@nirvaan.local": "female",
    "arun@nirvaan.local": "male",
}


def seed_demo_genders(db) -> int:
    """Set ``User.gender`` on demo accounts, new or existing. Idempotent.

    A no-op while the model has no ``gender`` column.
    """
    from app.models.user import User

    if not hasattr(User, "gender"):
        return 0
    db.flush()
    changed = 0
    for email, gender in DEMO_GENDERS.items():
        user = auth_service.get_user_by_email(db, email)
        if user is not None and user.gender != gender:
            user.gender = gender
            changed += 1
    return changed


# ---------------------------------------------------------------------------
# Demo activity for the demo accounts
# ---------------------------------------------------------------------------
#
# Gives priya@nirvaan.local a realistic ~4-week history so every page that
# reads the user's own rows (dashboard, journey, reflect, check, batch, talk,
# learn, family, privacy) has something to show. Each section checks for
# existing rows first, so re-running adds nothing.
#
# Product rules respected here: analysis statuses come from AnalysisStatus
# (never "safe" / "scam"), reflection labels from ReflectionLabel, and no text
# contains an OTP, PIN, card or account number (placeholders such as XXXX).

GOOD = ReflectionLabel.GOOD.value
REVIEW = ReflectionLabel.NEEDS_REVIEW.value
PRESENT = ReflectionLabel.PRESENT.value
DEVELOPING = ReflectionLabel.DEVELOPING.value


def _demo_at(days_ago: int, hour: int, minute: int = 0) -> datetime:
    """A UTC instant on the *local* calendar day ``days_ago`` days back.

    The heatmap and streak bucket activity by local date, so anchoring on the
    local day keeps the seeded streak intact whatever the server timezone.
    Never returns a time in the future.
    """
    now_local = datetime.now().astimezone()
    day = now_local.date() - timedelta(days=days_ago)
    midnight = datetime.combine(day, datetime.min.time()).replace(tzinfo=now_local.tzinfo)
    local = midnight.replace(hour=hour, minute=minute)
    if local > now_local - timedelta(minutes=5):
        # Later today than "now": pull it back, but keep it on the same day.
        local = max(now_local - timedelta(minutes=5 + days_ago), midnight + timedelta(seconds=30))
    return local.astimezone(timezone.utc)


# Each analysis: key, days_ago, hour, input kind, text, status, confidence,
# the four explainability panes, nlp extras and signals
# (signal_type, severity, confidence, evidence, explanation, verify_hint).
DEMO_ANALYSES = [
    {
        "key": "whatsapp_30pct",
        "days_ago": 0, "hour": 9, "kind": InputKind.TEXT,
        "text": (
            "Namaste! Join our VIP Trading Club. Guaranteed 30% monthly returns with "
            "zero risk. SEBI approved strategy. Only 5 seats left today - pay Rs 4,999 "
            "joining fee via UPI to confirm. 2,300 members already earning!"
        ),
        "status": AnalysisStatus.MULTIPLE_SIGNALS, "confidence": 0.91,
        "detected": (
            "A promise of fixed 30% monthly returns with no risk, a claim of SEBI "
            "approval without a registration number, a seat limit for today and a "
            "request for an upfront UPI payment."
        ),
        "why": (
            "Market-linked returns cannot be guaranteed. Pressure to pay quickly, plus "
            "an unverified regulatory claim, are patterns commonly seen in "
            "investment-tip frauds circulating on WhatsApp."
        ),
        "verify": (
            "Search the SEBI intermediary register for the club's registration "
            "number. Ask for written terms. Do not pay a joining fee until you have "
            "checked independently."
        ),
        "uncertain": (
            "We cannot see who sent this or confirm whether any registration exists. "
            "The signals describe the message, not the sender's intent."
        ),
        "claims": ["Guaranteed 30% monthly returns", "SEBI approved strategy"],
        "links": [],
        "signals": [
            (SignalType.GUARANTEED_RETURN, Severity.HIGH, 0.95, "Guaranteed 30% monthly returns",
             "Promises a fixed return on a market-linked product.",
             "Registered advisers are not allowed to promise fixed market returns."),
            (SignalType.UNVERIFIED_REGULATORY_CLAIM, Severity.HIGH, 0.82, "SEBI approved strategy",
             "Claims regulatory approval without a verifiable registration number.",
             "Look the name up on the SEBI intermediary search page."),
            (SignalType.LIMITED_TIME_PRESSURE, Severity.MEDIUM, 0.8, "Only 5 seats left today",
             "Creates a deadline that discourages careful checking.",
             "A genuine opportunity will still be there after you verify it."),
            (SignalType.PAYMENT_REQUEST, Severity.HIGH, 0.86, "pay Rs 4,999 joining fee via UPI",
             "Asks for money before any verifiable service is provided.",
             "Do not send money to a UPI ID you cannot link to a registered entity."),
            (SignalType.SOCIAL_PRESSURE, Severity.LOW, 0.6, "2,300 members already earning",
             "Uses claimed popularity as proof.",
             "Member counts and screenshots are easy to fabricate."),
        ],
    },
    {
        "key": "kyc_sms",
        "days_ago": 1, "hour": 19, "kind": InputKind.TEXT,
        "text": (
            "Dear Customer, your bank KYC has expired. Your account will be blocked "
            "within 24 hours. Update now: http://kyc-update-secure.in/verify and "
            "enter your debit card and OTP details."
        ),
        "status": AnalysisStatus.MULTIPLE_SIGNALS, "confidence": 0.93,
        "detected": (
            "A threat to block the account within 24 hours, a link to an unfamiliar "
            "domain, and a request to enter card and OTP details."
        ),
        "why": (
            "Banks do not ask for OTPs or full card details through SMS links. "
            "Urgent account-blocking warnings are commonly used to rush people into "
            "sharing credentials."
        ),
        "verify": (
            "Call the number printed on the back of your card or visit the branch. "
            "Open your bank's official app directly rather than tapping the link."
        ),
        "uncertain": (
            "We cannot confirm the sender ID or whether your KYC status has actually "
            "changed. Your bank can tell you this directly."
        ),
        "claims": ["KYC has expired", "Account will be blocked within 24 hours"],
        "links": ["http://kyc-update-secure.in/verify"],
        "signals": [
            (SignalType.URGENCY, Severity.HIGH, 0.88, "blocked within 24 hours",
             "Threatens a consequence on a short deadline.",
             "Your bank will give you time and an official channel to update KYC."),
            (SignalType.SUSPICIOUS_LINK, Severity.HIGH, 0.9, "http://kyc-update-secure.in/verify",
             "The link does not point to a known bank domain.",
             "Type your bank's address yourself instead of following SMS links."),
            (SignalType.OTP_REQUEST, Severity.HIGH, 0.94, "enter your debit card and OTP details",
             "Asks for a one-time password and card details.",
             "Never share an OTP with anyone, including people claiming to be the bank."),
            (SignalType.IMPERSONATION, Severity.MEDIUM, 0.7, "Dear Customer, your bank KYC",
             "Writes as if from your bank without naming it or using an official sender.",
             "Check whether the SMS came from your bank's registered sender ID."),
        ],
    },
    {
        "key": "telegram_tip",
        "days_ago": 4, "hour": 12, "kind": InputKind.IMAGE,
        "text": (
            "Telegram channel 'Smart Bull Calls': TOMORROW'S JACKPOT - buy XYZ Infra "
            "before 9:20 AM, target +40% this week. Insider news, don't miss it. "
            "Recovered all my losses with these calls!"
        ),
        "status": AnalysisStatus.MULTIPLE_SIGNALS, "confidence": 0.84,
        "detected": (
            "A screenshot of a Telegram stock tip promising +40% in a week, a claim "
            "of insider news, a morning deadline and a loss-recovery testimonial."
        ),
        "why": (
            "Short-term targets and 'insider' tips are typical of pump-and-dump "
            "groups. Acting on non-public information is also against market rules."
        ),
        "verify": (
            "Check whether the channel admin is a SEBI-registered research analyst. "
            "Read the company's official exchange filings rather than the tip."
        ),
        "uncertain": (
            "Text was read from a screenshot, so small details may be off. We cannot "
            "tell whether the channel is linked to the company."
        ),
        "claims": ["Target +40% this week", "Insider news"],
        "links": [],
        "ocr": 0.87,
        "signals": [
            (SignalType.UNREALISTIC_RETURN, Severity.HIGH, 0.85, "target +40% this week",
             "Projects a very large gain over a very short period.",
             "Compare with the stock's actual history on the exchange website."),
            (SignalType.FOMO, Severity.MEDIUM, 0.78, "don't miss it",
             "Plays on fear of missing out.",
             "Take a pause before acting on any tip that rushes you."),
            (SignalType.MISLEADING_TESTIMONIAL, Severity.MEDIUM, 0.66, "Recovered all my losses",
             "Uses an unverifiable personal story as evidence.",
             "Testimonials in tip groups are not independently checked."),
            (SignalType.LOSS_RECOVERY_PROMPT, Severity.LOW, 0.55, "Recovered all my losses",
             "Targets people who are trying to make back earlier losses.",
             "Decisions made to recover losses tend to take on more risk."),
        ],
    },
    {
        "key": "electricity",
        "days_ago": 9, "hour": 20, "kind": InputKind.TEXT,
        "text": (
            "Dear consumer, your electricity power will be disconnected tonight at "
            "9:30 PM because your previous month bill was not updated. Please "
            "immediately contact our electricity officer at 98XXXXXX10."
        ),
        "status": AnalysisStatus.MULTIPLE_SIGNALS, "confidence": 0.86,
        "detected": (
            "A same-night disconnection threat and a request to call a personal "
            "mobile number described as an 'electricity officer'."
        ),
        "why": (
            "Electricity boards send notices through official channels and do not "
            "ask you to call a personal number. Callers in this pattern often ask "
            "people to install screen-sharing apps."
        ),
        "verify": (
            "Check your bill status on the official electricity board website or "
            "app, or call the helpline printed on your last bill."
        ),
        "uncertain": "We cannot confirm whether there is a real pending bill on your account.",
        "claims": ["Power will be disconnected tonight"],
        "links": [],
        "signals": [
            (SignalType.URGENCY, Severity.HIGH, 0.87, "disconnected tonight at 9:30 PM",
             "A same-day deadline leaves little time to check.",
             "Utility disconnections follow written notices with time to respond."),
            (SignalType.FAKE_AUTHORITY, Severity.MEDIUM, 0.74, "our electricity officer",
             "Presents an individual as an official without verifiable details.",
             "Use only the helpline printed on your bill."),
            (SignalType.REMOTE_ACCESS_REQUEST, Severity.LOW, 0.4, "immediately contact",
             "Calls in this pattern often lead to requests to install remote-access apps.",
             "Do not install any app a caller asks you to."),
        ],
    },
    {
        "key": "bank_reminder",
        "days_ago": 15, "hour": 10, "kind": InputKind.TEXT,
        "text": (
            "Your credit card statement for September is ready. Total due Rs XXXX, "
            "due date 05-Oct. Pay via the bank app or net banking. We will never ask "
            "for your OTP or PIN."
        ),
        "status": AnalysisStatus.NO_OBVIOUS_SIGNALS, "confidence": 0.72,
        "detected": (
            "A statement reminder with a due date that points to the bank's own app "
            "and states it will never ask for an OTP or PIN."
        ),
        "why": (
            "Nothing here matched a known warning pattern: there is no link, no "
            "request for credentials and no unusual pressure."
        ),
        "verify": (
            "Confirm the amount due inside your bank app before paying. Payments are "
            "best made only through the official app or website."
        ),
        "uncertain": (
            "No obvious warning signals is not a guarantee the message is genuine. "
            "We cannot check the sender ID."
        ),
        "claims": [],
        "links": [],
        "signals": [],
    },
    {
        "key": "sip_confirmation",
        "days_ago": 22, "hour": 11, "kind": InputKind.TEXT,
        "text": (
            "Your SIP of Rs 2,000 in an equity mutual fund scheme has been processed "
            "on 03-Sep. Units will be allotted at the applicable NAV. Folio XXXX. "
            "View your statement on the AMC or CAMS website."
        ),
        "status": AnalysisStatus.NO_OBVIOUS_SIGNALS, "confidence": 0.7,
        "detected": (
            "A routine SIP processing confirmation that refers to NAV-based "
            "allotment and directs you to the AMC or registrar for statements."
        ),
        "why": (
            "The message makes no return promise and asks for nothing. Wording "
            "matches standard mutual fund transaction alerts."
        ),
        "verify": (
            "Match the amount and date with your consolidated account statement "
            "from CAMS or KFintech."
        ),
        "uncertain": (
            "We cannot confirm the sender. No obvious warning signals does not mean "
            "the message is guaranteed to be genuine."
        ),
        "claims": [],
        "links": [],
        "signals": [],
    },
]

# Items for the demo batch job; analyses are created alongside.
DEMO_BATCH_ITEMS = [
    {
        "name": "family_group_forward.png", "kind": InputKind.IMAGE,
        "text": (
            "Forwarded many times: Government scheme gives Rs 15,000 to every "
            "woman. Register today only at http://pm-yojana-claim.co - last date "
            "tonight!"
        ),
        "status": AnalysisStatus.MULTIPLE_SIGNALS, "confidence": 0.85,
        "detected": "A government-scheme claim with an unofficial link and a same-day deadline.",
        "links": ["http://pm-yojana-claim.co"],
        "signals": [
            (SignalType.FAKE_AUTHORITY, Severity.MEDIUM, 0.72, "Government scheme",
             "Uses a government name without an official source.",
             "Check scheme details on the official .gov.in portal."),
            (SignalType.SUSPICIOUS_LINK, Severity.HIGH, 0.86, "http://pm-yojana-claim.co",
             "The link is not on a government domain.",
             "Government scheme sites end in .gov.in or .nic.in."),
            (SignalType.URGENCY, Severity.MEDIUM, 0.76, "last date tonight",
             "Adds a short deadline.", "Official schemes publish dates well in advance."),
        ],
    },
    {
        "name": "loan_offer.txt", "kind": InputKind.TEXT,
        "text": (
            "Pre-approved instant loan of Rs 2,00,000 at 0% interest. Pay Rs 1,500 "
            "processing fee to activate. RBI registered."
        ),
        "status": AnalysisStatus.NEEDS_VERIFICATION, "confidence": 0.68,
        "detected": "An upfront fee for a loan and an RBI registration claim without details.",
        "signals": [
            (SignalType.PAYMENT_REQUEST, Severity.MEDIUM, 0.74, "Pay Rs 1,500 processing fee",
             "Asks for payment before a loan is disbursed.",
             "Regulated lenders deduct fees from the disbursal, with written terms."),
            (SignalType.UNVERIFIED_REGULATORY_CLAIM, Severity.MEDIUM, 0.6, "RBI registered",
             "Claims registration without a name or number to check.",
             "Search the lender on the RBI list of registered NBFCs."),
        ],
    },
    {
        "name": "insurance_renewal.pdf", "kind": InputKind.PDF,
        "text": (
            "Policy renewal notice. Premium due on 20-Oct. Renew through the insurer's "
            "website or your agent. Policy number XXXX."
        ),
        "status": AnalysisStatus.NO_OBVIOUS_SIGNALS, "confidence": 0.66,
        "detected": "A standard renewal notice directing you to the insurer's own channels.",
        "signals": [],
    },
    {
        "name": "crypto_doubling.png", "kind": InputKind.IMAGE,
        "text": (
            "Send 0.01 BTC and receive 0.02 BTC back within one hour. Limited "
            "promotion by our exchange. Thousands already doubled their coins."
        ),
        "status": AnalysisStatus.MULTIPLE_SIGNALS, "confidence": 0.9,
        "detected": "A promise to double crypto deposits within an hour, under a limited promotion.",
        "signals": [
            (SignalType.GUARANTEED_RETURN, Severity.HIGH, 0.92,
             "receive 0.02 BTC back within one hour",
             "Promises to double money in an hour.",
             "No legitimate exchange multiplies deposits on request."),
            (SignalType.LIMITED_TIME_PRESSURE, Severity.MEDIUM, 0.7, "Limited promotion",
             "Suggests the offer will vanish soon.",
             "Take time to verify before sending anything."),
            (SignalType.MISLEADING_TESTIMONIAL, Severity.LOW, 0.55, "Thousands already doubled",
             "Uses unverifiable crowd claims.", "Claimed results are not evidence."),
        ],
    },
    {
        "name": "blurry_screenshot.jpg", "kind": InputKind.IMAGE,
        "text": None,  # failed: the text could not be read
        "error": "Text could not be read from the image. Try a clearer screenshot.",
    },
]

# Reflection sessions: days_ago, hour, five labels (reason_clarity,
# evidence_quality, time_pressure, external_influence, understanding),
# summary, pause seconds, completed?, linked analysis key.
DEMO_REFLECTIONS = [
    (0, 9, (REVIEW, REVIEW, PRESENT, PRESENT, DEVELOPING),
     "Paused before paying the joining fee for the WhatsApp trading club. I could "
     "not find a SEBI registration and the 30% promise felt too good. Decided to "
     "wait and ask my son.", 180, True, "whatsapp_30pct"),
    (1, 20, (GOOD, GOOD, PRESENT, GOOD, GOOD),
     "Got a KYC SMS with a link. Remembered that banks never ask for OTP. Called "
     "the bank helpline instead - my KYC was fine.", 120, True, "kyc_sms"),
    (2, 18, (GOOD, DEVELOPING, GOOD, GOOD, DEVELOPING),
     "Thinking about increasing my monthly SIP. My reason is clear (retirement), but "
     "I want to understand expense ratios better first.", 240, True, None),
    (3, 21, (GOOD, GOOD, GOOD, GOOD, GOOD),
     "Reviewed my emergency fund before moving money into a fixed deposit. No rush, "
     "compared rates on the bank websites myself.", 150, True, None),
    (5, 13, (REVIEW, REVIEW, PRESENT, PRESENT, REVIEW),
     "A friend in my building keeps talking about a stock tip group. Felt pressure "
     "to join. Wrote down what I actually know - very little.", 300, True, "telegram_tip"),
    (8, 19, (GOOD, GOOD, GOOD, PRESENT, GOOD),
     "Relative suggested a ULIP. Read the brochure fully and noted the lock-in and "
     "charges. Not deciding this week.", 210, True, None),
    (12, 10, (GOOD, DEVELOPING, GOOD, GOOD, DEVELOPING),
     "Planning gold purchase for Diwali. Compared digital gold vs gold ETF basics; "
     "still learning the differences.", 90, True, None),
    # Started but not finished: counts as activity, not as a reflection.
    (13, 22, (None, None, None, None, None), "", 0, False, None),
    (17, 16, (GOOD, GOOD, PRESENT, GOOD, GOOD),
     "Insurance agent called about a 'last day' offer. Asked for the documents by "
     "email and took time to read them.", 165, True, None),
    (24, 11, (DEVELOPING, REVIEW, GOOD, GOOD, DEVELOPING),
     "First reflection. Wanted to understand why I keep checking market apps every "
     "hour. Mostly worry, not a plan.", 60, True, None),
]

# days_ago, hour, title, body, mood, shared with family
DEMO_JOURNALS = [
    (0, 10, "Waited before paying",
     "The 30% returns message looked exciting, but after the pause it was clear I "
     "had no way to verify it. Will discuss with Arun this evening.",
     "Calmer after pausing", False),
    (3, 21, "Emergency fund check",
     "Six months of expenses are now set aside. Feeling more in control of where "
     "the money is.", "Steady", False),
    (10, 8, "Questions for the bank",
     "Ask about SIP step-up options and how the auto-debit mandate can be paused "
     "if needed.", None, True),
    (19, 20, "Noticing the urge",
     "I opened the trading app six times today. Going to check it only once in the "
     "evening this week.", "Restless", False),
]

# slug, percent, completed days_ago (None = in progress), last viewed days_ago, bookmarked
DEMO_LEARNING = [
    ("guaranteed-return-warning", 100, 4, 4, False),
    ("never-share-otp", 100, 6, 6, True),
    ("what-is-a-mutual-fund", 100, 11, 11, False),
    ("understanding-sip", 45, None, 2, False),
    ("recognising-pressure-tactics", 100, 14, 14, False),
]

# days_ago, hour, kind, title, body, icon, link, read?
DEMO_NOTIFICATIONS = [
    (0, 9, "check_alert", "A message you checked had multiple safety signals",
     "Take a moment before acting. Review what to verify on the Check page.",
     "warning", "/check", False),
    (1, 8, "weekly_summary", "Your weekly reflection summary is ready",
     "See the patterns in your recent reflections in My Journey.",
     "insights", "/journey", True),
    (6, 18, "learning", "New lesson: recognising pressure tactics",
     "A short read on spotting urgency and social pressure.",
     "school", "/learn", True),
    (14, 12, "family", "Arun is now a trusted family member",
     "He can see only the scopes you shared. You can change this anytime in Family Mode.",
     "family_restroom", "/family", True),
]

DEMO_VOICE_TURNS = [
    ("user", "Someone says an app gives 2% daily returns. Is that possible?"),
    ("assistant", "A fixed 2% a day would be more than 600% a year, far beyond what "
     "market-linked products have historically delivered. Promises like this are a "
     "common warning signal. Would you like to pause and reflect on it, or check the "
     "message itself?"),
    ("user", "How do I check if an adviser is registered?"),
    ("assistant", "You can search the adviser's name or registration number on SEBI's "
     "intermediary search page. A registered adviser will also give you written terms "
     "and will not promise fixed returns."),
]


def _demo_analysis(db, user, spec: dict, at: datetime, batch_item_id=None) -> MessageAnalysis:
    ocr = spec["kind"] in (InputKind.IMAGE, InputKind.PDF)
    analysis = MessageAnalysis(
        user_id=user.id,
        batch_item_id=batch_item_id,
        input_kind=spec["kind"].value,
        raw_text=spec["text"],
        ocr_used=ocr,
        ocr_confidence=spec.get("ocr", 0.9) if ocr else None,
        detected_language="en",
        language_confidence=0.97,
        status=spec["status"].value,
        confidence=spec["confidence"],
        nlp_result={"claims": spec.get("claims", []), "links": spec.get("links", [])},
        what_we_detected=spec["detected"],
        why_it_matters=spec.get(
            "why", "These patterns are commonly seen in misleading financial messages."
        ),
        what_to_verify=spec.get(
            "verify",
            "Confirm the claim through an official website or helpline you find yourself.",
        ),
        what_is_uncertain=spec.get(
            "uncertain", "We cannot confirm who sent this or what their intent is."
        ),
        guardrail_action="ALLOW",
        ai_provider="local",
        processing_ms=420,
        created_at=at,
        updated_at=at,
    )
    text = spec["text"]
    for stype, sev, conf, evidence, explanation, hint in spec["signals"]:
        start = text.find(evidence)
        analysis.signals.append(
            AnalysisSignal(
                signal_type=stype.value,
                severity=sev.value,
                confidence=conf,
                evidence=evidence,
                evidence_start=start if start >= 0 else None,
                evidence_end=start + len(evidence) if start >= 0 else None,
                explanation=explanation,
                verify_hint=hint,
                detector="rule",
                created_at=at,
                updated_at=at,
            )
        )
    db.add(analysis)
    return analysis


def seed_demo_activity(db) -> dict[str, int]:
    """Seed Priya's demo history and the Priya -> Arun family link.

    Idempotent: each section is skipped when Priya already has rows of that
    kind (learning progress is checked per lesson, the family link per pair).
    """
    added: dict[str, int] = {}
    priya = auth_service.get_user_by_email(db, "priya@nirvaan.local")
    arun = auth_service.get_user_by_email(db, "arun@nirvaan.local")
    if priya is None:
        return added

    def has_rows(model, column) -> bool:
        stmt = select(func.count()).select_from(model).where(column == priya.id)
        return (db.execute(stmt).scalar() or 0) > 0

    # Make the account as old as its history (member-since on My Journey).
    started = _demo_at(35, 10)
    created = priya.created_at
    if created is not None and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if created is None or created > started:
        priya.created_at = started

    # Privacy switches consistent with the seeded voice transcript and family link.
    if priya.privacy is not None:
        priya.privacy.store_voice_transcripts = True
        priya.privacy.allow_family_access = True

    # --- message analyses + batch job -------------------------------------
    analyses: dict[str, MessageAnalysis] = {}
    if not has_rows(MessageAnalysis, MessageAnalysis.user_id):
        for spec in DEMO_ANALYSES:
            analyses[spec["key"]] = _demo_analysis(
                db, priya, spec, _demo_at(spec["days_ago"], spec["hour"])
            )

        job_at = _demo_at(7, 15)
        job = BatchJob(
            user_id=priya.id,
            label="Family WhatsApp forwards",
            status=JobStatus.COMPLETED.value,
            started_at=job_at,
            finished_at=job_at + timedelta(seconds=48),
            created_at=job_at,
            updated_at=job_at + timedelta(seconds=48),
        )
        db.add(job)
        db.flush()
        rollup = {s.value: 0 for s in AnalysisStatus}
        done = failed = 0
        for position, spec in enumerate(DEMO_BATCH_ITEMS):
            item_at = job_at + timedelta(seconds=8 * (position + 1))
            item = BatchItem(
                job_id=job.id,
                position=position,
                display_name=spec["name"],
                created_at=item_at,
                updated_at=item_at,
            )
            db.add(item)
            db.flush()
            if spec.get("text") is None:
                item.status = JobStatus.FAILED.value
                item.error = spec["error"]
                failed += 1
                continue
            analysis = _demo_analysis(db, priya, spec, item_at, batch_item_id=item.id)
            db.flush()
            item.analysis_id = analysis.id
            item.status = JobStatus.COMPLETED.value
            item.result_status = spec["status"].value
            rollup[spec["status"].value] += 1
            done += 1
        job.total_items = len(DEMO_BATCH_ITEMS)
        job.completed_items = done
        job.failed_items = failed
        job.summary = rollup
        added["analyses"] = len(DEMO_ANALYSES) + done
        added["batch jobs"] = 1
        db.flush()
    else:
        texts = {spec["text"]: spec["key"] for spec in DEMO_ANALYSES}
        for a in db.execute(
            select(MessageAnalysis).where(MessageAnalysis.user_id == priya.id)
        ).scalars():
            if a.raw_text in texts:
                analyses[texts[a.raw_text]] = a

    # --- reflections ------------------------------------------------------
    if not has_rows(ReflectionSession, ReflectionSession.user_id):
        for days_ago, hour, labels, summary, pause, completed, link in DEMO_REFLECTIONS:
            at = _demo_at(days_ago, hour)
            finished = min(
                at + timedelta(seconds=pause + 240), datetime.now(timezone.utc)
            ) if completed else None
            linked = analyses.get(link) if link else None
            db.add(
                ReflectionSession(
                    user_id=priya.id,
                    analysis_id=linked.id if linked is not None else None,
                    language="en",
                    completed_at=finished,
                    reason_clarity=labels[0],
                    evidence_quality=labels[1],
                    time_pressure=labels[2],
                    external_influence=labels[3],
                    understanding=labels[4],
                    summary=summary,
                    signals_noticed=(
                        {
                            "time_pressure": labels[2] == PRESENT,
                            "external_influence": labels[3] == PRESENT,
                        }
                        if completed
                        else None
                    ),
                    pause_completed=completed and pause > 0,
                    pause_seconds=pause,
                    created_at=at,
                    updated_at=finished or at,
                )
            )
        added["reflections"] = len(DEMO_REFLECTIONS)

    # --- journal ----------------------------------------------------------
    if not has_rows(JournalEntry, JournalEntry.user_id):
        for days_ago, hour, title, body, mood, shared in DEMO_JOURNALS:
            at = _demo_at(days_ago, hour)
            db.add(
                JournalEntry(
                    user_id=priya.id,
                    title=title,
                    body=body,
                    language="en",
                    mood_note=mood,
                    shared_with_family=shared,
                    created_at=at,
                    updated_at=at,
                )
            )
        added["journal entries"] = len(DEMO_JOURNALS)

    # --- learning progress (unique per user + lesson) ---------------------
    n = 0
    for slug, percent, done_ago, viewed_ago, bookmarked in DEMO_LEARNING:
        content = db.execute(
            select(LearningContent).where(LearningContent.slug == slug)
        ).scalar_one_or_none()
        if content is None:
            continue
        exists = db.execute(
            select(LearningProgress.id).where(
                LearningProgress.user_id == priya.id,
                LearningProgress.content_id == content.id,
            )
        ).first()
        if exists is not None:
            continue
        viewed = _demo_at(viewed_ago, 17)
        db.add(
            LearningProgress(
                user_id=priya.id,
                content_id=content.id,
                percent=percent,
                completed_at=viewed if done_ago is not None else None,
                last_viewed_at=viewed,
                view_count=2 if done_ago is not None else 1,
                bookmarked=bookmarked,
                created_at=viewed - timedelta(minutes=10),
                updated_at=viewed,
            )
        )
        n += 1
    if n:
        added["learning progress"] = n

    # --- notifications ----------------------------------------------------
    if not has_rows(Notification, Notification.user_id):
        for days_ago, hour, kind, title, body, icon, link, read in DEMO_NOTIFICATIONS:
            at = _demo_at(days_ago, hour)
            db.add(
                Notification(
                    user_id=priya.id,
                    kind=kind,
                    title=title,
                    body=body,
                    icon=icon,
                    link=link,
                    read_at=at + timedelta(minutes=30) if read else None,
                    created_at=at,
                    updated_at=at,
                )
            )
        added["notifications"] = len(DEMO_NOTIFICATIONS)

    # --- voice session with a retained transcript -------------------------
    if not has_rows(VoiceSession, VoiceSession.user_id):
        at = _demo_at(2, 11)
        session = VoiceSession(
            user_id=priya.id,
            language="en",
            stt_provider="browser",
            tts_provider="browser",
            ai_provider="local",
            title="Daily return app question",
            ended_at=at + timedelta(minutes=4),
            turn_count=len(DEMO_VOICE_TURNS),
            transcripts_retained=True,
            created_at=at,
            updated_at=at + timedelta(minutes=4),
        )
        for i, (role, content) in enumerate(DEMO_VOICE_TURNS):
            t = at + timedelta(seconds=50 * i)
            is_user = role == "user"
            session.messages.append(
                VoiceMessage(
                    role=role,
                    content=content,
                    language="en",
                    stt_confidence=0.92 if is_user else None,
                    audio_seconds=4.5 if is_user else None,
                    guardrail_action=None if is_user else "ALLOW",
                    latency_ms=None if is_user else 900,
                    created_at=t,
                    updated_at=t,
                )
            )
        db.add(session)
        added["voice sessions"] = 1

    # --- family link: Priya (owner) -> Arun (assistant) -------------------
    if arun is not None:
        rel = db.execute(
            select(FamilyRelationship).where(
                FamilyRelationship.owner_user_id == priya.id,
                FamilyRelationship.assistant_user_id == arun.id,
            )
        ).scalar_one_or_none()
        if rel is None:
            at = _demo_at(14, 12)
            rel = FamilyRelationship(
                owner_user_id=priya.id,
                assistant_user_id=arun.id,
                relationship_label="son",
                consent_granted_at=at,
                consent_text_version="v1",
                active=True,
                created_at=at,
                updated_at=at,
            )
            for scope in (PermissionScope.SAFETY_ONLY, PermissionScope.LEARNING_ONLY):
                rel.permissions.append(
                    FamilyPermission(
                        scope=scope.value,
                        granted=True,
                        granted_at=at,
                        created_at=at,
                        updated_at=at,
                    )
                )
            db.add(rel)
            added["family links"] = 1

    return added


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--demo-users", action="store_true", help="also create demo accounts"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="DROP every table first. Destroys all data.",
    )
    args = parser.parse_args()

    if args.reset:
        confirm = input("This deletes all data. Type 'yes' to continue: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            return 1
        Base.metadata.drop_all(engine)
        print("dropped all tables")

    Base.metadata.create_all(engine)
    print(f"schema ready ({len(Base.metadata.tables)} tables)")

    with session_scope() as db:
        print(f"  roles          +{seed_roles(db)}")
        print(f"  feature flags  +{seed_flags(db)}")
        print(f"  safety rules   +{seed_safety_rules(db)}")
        print(f"  learning cards +{seed_learning(db)}")
        print(f"  market scenarios +{seed_market(db)}")
        if args.demo_users:
            count = seed_demo_users(db)
            print(f"  demo users     +{count}")
            if count:
                print("\n  Demo credentials:")
                for name, email, password, _lang, role in DEMO_USERS:
                    print(f"    {role.value:17} {email:24} {password}")
            db.flush()
            print(f"  demo genders   +{seed_demo_genders(db)}")
            activity = seed_demo_activity(db)
            for label, n in activity.items():
                print(f"  demo {label:17} +{n}")
            if not activity:
                print("  demo activity  +0 (already present)")

    print("\nseed complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
