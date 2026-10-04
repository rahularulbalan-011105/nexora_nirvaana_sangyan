"""Lesson text for Learn & Explore, per language and per explanation mode.

``LearningContent`` rows (seeded by ``scripts/seed.py``) own a lesson's identity:
slug, category, ordering, reading time and the per-user progress rows hang off
them. The slug column is unique, so a row cannot exist once per language. The
actual lesson text therefore lives here, keyed by ``slug -> language -> mode``,
which keeps every language complete and side by side for review.

Modes: ``simple``, ``detailed``, ``example``, ``analogy``. Paragraphs are
separated by a blank line. Everything here is general education: no product,
no buy/sell/hold view, no prediction, no personalised advice.
"""
from __future__ import annotations

LANGUAGES = ("en", "hi", "ta")
MODES = ("simple", "detailed", "example", "analogy")

# BCP-47 tags handed to the browser's speech synthesiser.
SPEECH_LANG = {"en": "en-IN", "hi": "hi-IN", "ta": "ta-IN"}

# ---------------------------------------------------------------------------
# Trusted external resources (official regulator / government sites only).
# Each URL was checked to respond before being listed here.
# ---------------------------------------------------------------------------
RESOURCES: dict[str, dict] = {
    "sebi_investor": {
        "name": "SEBI Investor Website",
        "url": "https://investor.sebi.gov.in/",
        "about": {
            "en": "SEBI's investor education site: basics, warnings and guides.",
            "hi": "सेबी की निवेशक शिक्षा वेबसाइट: बुनियादी बातें, चेतावनियाँ और गाइड।",
            "ta": "செபியின் முதலீட்டாளர் கல்வி இணையதளம்: அடிப்படைகள், எச்சரிக்கைகள், வழிகாட்டிகள்.",
        },
    },
    "sebi": {
        "name": "Securities and Exchange Board of India (SEBI)",
        "url": "https://www.sebi.gov.in/",
        "about": {
            "en": "The market regulator. Look up whether an intermediary is registered.",
            "hi": "बाज़ार नियामक। देखें कि कोई मध्यस्थ पंजीकृत है या नहीं।",
            "ta": "சந்தை ஒழுங்குமுறை அமைப்பு. ஒரு இடைத்தரகர் பதிவு பெற்றவரா என்று இங்கே பார்க்கலாம்.",
        },
    },
    "scores": {
        "name": "SEBI SCORES complaint portal",
        "url": "https://scores.sebi.gov.in/",
        "about": {
            "en": "File and track a complaint against a SEBI-registered entity.",
            "hi": "सेबी-पंजीकृत संस्था के ख़िलाफ़ शिकायत दर्ज करें और उसकी स्थिति देखें।",
            "ta": "செபியில் பதிவு பெற்ற நிறுவனத்தின் மீது புகார் அளித்து, அதன் நிலையைப் பார்க்கலாம்.",
        },
    },
    "amfi": {
        "name": "AMFI Investor section",
        "url": "https://www.amfiindia.com/investor",
        "about": {
            "en": "Mutual fund industry body: investor education and fund-house basics.",
            "hi": "म्यूचुअल फंड उद्योग संस्था: निवेशक शिक्षा और फंड हाउस की जानकारी।",
            "ta": "மியூச்சுவல் ஃபண்ட் தொழில் அமைப்பு: முதலீட்டாளர் கல்வி, ஃபண்ட் நிறுவனத் தகவல்.",
        },
    },
    "rbi": {
        "name": "Reserve Bank of India (RBI)",
        "url": "https://www.rbi.org.in/",
        "about": {
            "en": "The banking regulator. Official notices and lists of regulated entities.",
            "hi": "बैंकिंग नियामक। आधिकारिक सूचनाएँ और विनियमित संस्थाओं की सूची।",
            "ta": "வங்கி ஒழுங்குமுறை அமைப்பு. அதிகாரப்பூர்வ அறிவிப்புகள், ஒழுங்குபடுத்தப்பட்ட நிறுவனங்களின் பட்டியல்.",
        },
    },
    "rbi_kehta_hai": {
        "name": "RBI Kehta Hai",
        "url": "https://rbikehtahai.rbi.org.in/",
        "about": {
            "en": "RBI's public awareness campaign on safe banking and digital payments.",
            "hi": "सुरक्षित बैंकिंग और डिजिटल भुगतान पर आरबीआई का जन-जागरूकता अभियान।",
            "ta": "பாதுகாப்பான வங்கி மற்றும் டிஜிட்டல் பணப் பரிமாற்றம் குறித்த ஆர்பிஐ விழிப்புணர்வு இயக்கம்.",
        },
    },
    "rbi_cms": {
        "name": "RBI Complaint Management System",
        "url": "https://cms.rbi.org.in/",
        "about": {
            "en": "Complain to the RBI Ombudsman if your bank does not resolve an issue.",
            "hi": "अगर बैंक आपकी समस्या हल न करे तो आरबीआई लोकपाल को शिकायत करें।",
            "ta": "உங்கள் வங்கி பிரச்சனையைத் தீர்க்காவிட்டால் ஆர்பிஐ குறைதீர்ப்பாளரிடம் புகார் அளிக்கலாம்.",
        },
    },
    "sachet": {
        "name": "RBI Sachet",
        "url": "https://sachet.rbi.org.in/",
        "about": {
            "en": "Check whether an entity may accept deposits, and report illegal schemes.",
            "hi": "देखें कि कोई संस्था जमा ले सकती है या नहीं, और अवैध योजनाओं की शिकायत करें।",
            "ta": "ஒரு நிறுவனம் வைப்புத்தொகை வாங்க அனுமதி உள்ளதா என்று பார்த்து, சட்டவிரோத திட்டங்களைப் புகாரளிக்கலாம்.",
        },
    },
    "cybercrime": {
        "name": "National Cyber Crime Reporting Portal",
        "url": "https://cybercrime.gov.in/",
        "about": {
            "en": "Report online financial fraud. Helpline: 1930.",
            "hi": "ऑनलाइन वित्तीय धोखाधड़ी की शिकायत करें। हेल्पलाइन: 1930।",
            "ta": "ஆன்லைன் நிதி மோசடியைப் புகாரளிக்கலாம். உதவி எண்: 1930.",
        },
    },
    "ncfe": {
        "name": "National Centre for Financial Education (NCFE)",
        "url": "https://ncfe.org.in/",
        "about": {
            "en": "Free, non-commercial financial literacy material.",
            "hi": "मुफ़्त, गैर-व्यावसायिक वित्तीय साक्षरता सामग्री।",
            "ta": "இலவச, வணிக நோக்கமற்ற நிதி அறிவு கல்விப் பொருட்கள்.",
        },
    },
}


# ---------------------------------------------------------------------------
# Lessons
# ---------------------------------------------------------------------------
LESSONS: dict[str, dict] = {
    # ------------------------------------------------------------------
    "what-is-a-mutual-fund": {
        "resources": ["amfi", "sebi_investor", "sebi"],
        "en": {
            "title": "What is a mutual fund?",
            "summary": "A pooled investment managed to a stated objective, and what that means for your money.",
            "simple": "Many people put their money together in one pool. A professional manager invests that pool in shares, bonds or both, following a goal written down in advance.\n\n"
                      "You get units of the fund. If the investments gain value, your units are worth more. If they lose value, your units are worth less.\n\n"
                      "Nobody can promise you a profit from a mutual fund.",
            "detailed": "A mutual fund collects money from many investors and invests the pool according to an objective stated in its scheme documents, for example \"invest mainly in large companies\" or \"invest mainly in government bonds\".\n\n"
                        "You own units of the fund, not the shares or bonds directly. The value of one unit is called the NAV (net asset value). It is calculated every business day from the value of everything the fund holds.\n\n"
                        "Every fund charges a yearly fee called the expense ratio. It is taken out of the fund's assets whether the fund gains or loses, so costs reduce what you keep.\n\n"
                        "Mutual funds in India are regulated by SEBI. Regulation means rules on disclosure and how the money is held. It does not mean returns are protected.\n\n"
                        "Returns are not guaranteed and can be negative. Past performance describes what already happened; it does not decide what happens next.",
            "example": "Suppose 1,000 people each put ₹1,000 into a new fund. The pool is ₹10,00,000 and each person gets 100 units at ₹10 per unit.\n\n"
                       "After some months the investments in the pool are worth ₹11,00,000. Each unit is now worth about ₹11, so each person's 100 units are worth about ₹1,100, before costs.\n\n"
                       "If the investments had fallen to ₹9,00,000 instead, each unit would be worth about ₹9 and each person's units about ₹900. The same pooling works in both directions.",
            "analogy": "Think of a group of neighbours who each give a little money to buy a big basket of fruit together from the wholesale market, because one person alone could not buy so much variety.\n\n"
                       "One trusted person does the buying, following rules everyone agreed on. Each neighbour owns a share of the basket in proportion to what they paid.\n\n"
                       "If some fruit spoils, everyone's share loses a little value; if prices rise, everyone's share is worth more. The basket spreads the risk, but it does not remove it.",
        },
        "hi": {
            "title": "म्यूचुअल फंड क्या है?",
            "summary": "कई लोगों का इकट्ठा पैसा, जिसे एक तय लक्ष्य के अनुसार निवेश किया जाता है, और इसका आपके पैसे पर क्या मतलब है।",
            "simple": "बहुत से लोग अपना पैसा एक साथ एक जगह जमा करते हैं। एक पेशेवर मैनेजर उस पैसे को पहले से लिखे लक्ष्य के अनुसार शेयरों, बॉन्ड या दोनों में लगाता है।\n\n"
                      "आपको फंड की यूनिट मिलती हैं। निवेश की कीमत बढ़े तो आपकी यूनिट की कीमत बढ़ती है। घटे तो आपकी यूनिट की कीमत भी घटती है।\n\n"
                      "म्यूचुअल फंड में कोई भी मुनाफ़े का वादा नहीं कर सकता।",
            "detailed": "म्यूचुअल फंड कई निवेशकों से पैसा इकट्ठा करता है और उसे योजना के दस्तावेज़ में लिखे उद्देश्य के अनुसार लगाता है, जैसे \"मुख्य रूप से बड़ी कंपनियों में\" या \"मुख्य रूप से सरकारी बॉन्ड में\"।\n\n"
                        "आप सीधे शेयर या बॉन्ड के मालिक नहीं होते, बल्कि फंड की यूनिट के मालिक होते हैं। एक यूनिट की कीमत को एनएवी (NAV) कहते हैं। यह हर कारोबारी दिन फंड की सारी संपत्ति की कीमत से निकाली जाती है।\n\n"
                        "हर फंड एक सालाना शुल्क लेता है जिसे एक्सपेंस रेशियो कहते हैं। फंड को फ़ायदा हो या नुकसान, यह शुल्क कटता है, इसलिए खर्च आपके हिस्से को कम करता है।\n\n"
                        "भारत में म्यूचुअल फंड सेबी (SEBI) के नियमों के तहत चलते हैं। नियमों का मतलब है जानकारी देने और पैसा रखने के नियम। इसका मतलब यह नहीं कि रिटर्न सुरक्षित है।\n\n"
                        "रिटर्न की कोई गारंटी नहीं होती और यह नकारात्मक भी हो सकता है। पिछला प्रदर्शन बताता है कि पहले क्या हुआ; आगे क्या होगा, यह तय नहीं करता।",
            "example": "मान लीजिए 1,000 लोग एक नए फंड में ₹1,000-₹1,000 लगाते हैं। कुल पैसा ₹10,00,000 हुआ और हर व्यक्ति को ₹10 प्रति यूनिट के भाव से 100 यूनिट मिलीं।\n\n"
                       "कुछ महीनों बाद फंड के निवेश की कीमत ₹11,00,000 हो जाती है। अब एक यूनिट लगभग ₹11 की है, यानी हर व्यक्ति की 100 यूनिट लगभग ₹1,100 की, खर्च से पहले।\n\n"
                       "अगर निवेश घटकर ₹9,00,000 के रह जाते, तो एक यूनिट लगभग ₹9 की होती और हर व्यक्ति की यूनिट लगभग ₹900 की। इकट्ठा निवेश दोनों तरफ़ असर करता है।",
            "analogy": "सोचिए कुछ पड़ोसी थोड़ा-थोड़ा पैसा मिलाकर मंडी से फलों की एक बड़ी टोकरी ख़रीदते हैं, क्योंकि अकेले कोई इतनी किस्में नहीं ख़रीद सकता।\n\n"
                       "एक भरोसेमंद व्यक्ति सबके तय किए नियमों के अनुसार ख़रीदारी करता है। हर पड़ोसी का टोकरी में उतना हिस्सा है जितना उसने पैसा दिया।\n\n"
                       "कुछ फल ख़राब हो जाएँ तो सबका हिस्सा थोड़ा घटता है; दाम बढ़ें तो सबका हिस्सा बढ़ता है। टोकरी जोखिम को बाँटती है, ख़त्म नहीं करती।",
        },
        "ta": {
            "title": "மியூச்சுவல் ஃபண்ட் என்றால் என்ன?",
            "summary": "பலரின் பணத்தை ஒன்றாகச் சேர்த்து, முன்பே சொன்ன இலக்கின்படி முதலீடு செய்வது, அது உங்கள் பணத்துக்கு என்ன அர்த்தம் என்பது.",
            "simple": "பலர் தங்கள் பணத்தை ஒரே இடத்தில் சேர்க்கிறார்கள். ஒரு தொழில்முறை மேலாளர் அந்தப் பணத்தை முன்பே எழுதிய இலக்கின்படி பங்குகள், பத்திரங்கள் அல்லது இரண்டிலும் முதலீடு செய்கிறார்.\n\n"
                      "உங்களுக்கு ஃபண்டின் யூனிட்கள் கிடைக்கும். முதலீடுகளின் மதிப்பு கூடினால் உங்கள் யூனிட்களின் மதிப்பும் கூடும். குறைந்தால் உங்கள் யூனிட்களின் மதிப்பும் குறையும்.\n\n"
                      "மியூச்சுவல் ஃபண்டில் லாபம் உறுதி என்று யாரும் வாக்குறுதி தர முடியாது.",
            "detailed": "மியூச்சுவல் ஃபண்ட் பல முதலீட்டாளர்களிடமிருந்து பணத்தைத் திரட்டி, திட்ட ஆவணத்தில் எழுதிய நோக்கத்தின்படி முதலீடு செய்கிறது, உதாரணமாக \"பெரும்பாலும் பெரிய நிறுவனங்களில்\" அல்லது \"பெரும்பாலும் அரசுப் பத்திரங்களில்\".\n\n"
                        "நீங்கள் பங்குகளையோ பத்திரங்களையோ நேரடியாக வைத்திருப்பதில்லை; ஃபண்டின் யூனிட்களை வைத்திருக்கிறீர்கள். ஒரு யூனிட்டின் மதிப்பு என்ஏவி (NAV) எனப்படும். ஃபண்ட் வைத்திருக்கும் அனைத்தின் மதிப்பைக் கொண்டு இது ஒவ்வொரு வணிக நாளும் கணக்கிடப்படுகிறது.\n\n"
                        "ஒவ்வொரு ஃபண்டும் செலவு விகிதம் (expense ratio) என்ற ஆண்டுக் கட்டணம் வசூலிக்கிறது. ஃபண்ட் லாபம் அடைந்தாலும் நஷ்டம் அடைந்தாலும் இது கழிக்கப்படும்; எனவே செலவுகள் உங்களுக்கு மிஞ்சுவதைக் குறைக்கின்றன.\n\n"
                        "இந்தியாவில் மியூச்சுவல் ஃபண்டுகள் செபி (SEBI) விதிகளின் கீழ் இயங்குகின்றன. விதிகள் என்றால் தகவல் வெளியிடுதல், பணத்தைப் பாதுகாத்து வைத்தல் பற்றிய விதிகள். வருமானம் பாதுகாக்கப்படும் என்று அர்த்தமில்லை.\n\n"
                        "வருமானம் உறுதியானது அல்ல; எதிர்மறையாகவும் இருக்கலாம். கடந்த கால செயல்திறன் ஏற்கனவே நடந்ததைச் சொல்கிறது; அடுத்து என்ன நடக்கும் என்பதைத் தீர்மானிக்காது.",
            "example": "1,000 பேர் ஒவ்வொருவரும் ஒரு புதிய ஃபண்டில் ₹1,000 போடுகிறார்கள் என்று வைத்துக்கொள்வோம். மொத்தம் ₹10,00,000. ஒவ்வொருவருக்கும் யூனிட் ஒன்றுக்கு ₹10 விலையில் 100 யூனிட்கள் கிடைக்கின்றன.\n\n"
                       "சில மாதங்கள் கழித்து முதலீடுகளின் மதிப்பு ₹11,00,000 ஆகிறது. இப்போது ஒரு யூனிட் சுமார் ₹11; ஒவ்வொருவரின் 100 யூனிட்களும் சுமார் ₹1,100, செலவுகளுக்கு முன்.\n\n"
                       "மாறாக முதலீடுகள் ₹9,00,000 ஆகக் குறைந்திருந்தால், ஒரு யூனிட் சுமார் ₹9, ஒவ்வொருவரின் யூனிட்களும் சுமார் ₹900. சேர்ந்து முதலீடு செய்வது இரண்டு திசையிலும் வேலை செய்யும்.",
            "analogy": "சில அண்டை வீட்டார் ஒவ்வொருவரும் கொஞ்சம் பணம் போட்டு, மொத்தச் சந்தையிலிருந்து ஒரு பெரிய பழக் கூடையை வாங்குகிறார்கள் என்று நினைத்துப் பாருங்கள். தனியாக ஒருவரால் இத்தனை வகைகளை வாங்க முடியாது.\n\n"
                       "அனைவரும் ஒப்புக்கொண்ட விதிகளின்படி நம்பகமான ஒருவர் வாங்குகிறார். ஒவ்வொருவரும் கொடுத்த பணத்தின் அளவுக்கு கூடையில் பங்கு உண்டு.\n\n"
                       "சில பழங்கள் கெட்டுப்போனால் அனைவரின் பங்கும் கொஞ்சம் குறையும்; விலை ஏறினால் அனைவரின் பங்கும் கூடும். கூடை ஆபத்தைப் பகிர்கிறது, ஆனால் நீக்குவதில்லை.",
        },
    },
    # ------------------------------------------------------------------
    "understanding-sip": {
        "resources": ["amfi", "sebi_investor", "ncfe"],
        "en": {
            "title": "What a SIP does, and does not, do",
            "summary": "Investing a fixed amount regularly spreads out your entry points. It does not remove risk.",
            "simple": "SIP means Systematic Investment Plan. You put the same amount into a mutual fund at regular times, for example every month.\n\n"
                      "When the price is low your money buys more units; when the price is high it buys fewer. This spreads out the price you pay.\n\n"
                      "A SIP is a way of investing, not a product. It does not guarantee a profit and it does not stop losses.",
            "detailed": "A Systematic Investment Plan means investing a fixed amount at regular intervals instead of all at once. It is usually set up as an automatic debit from a bank account.\n\n"
                        "What it does: it spreads your purchases across different price levels, so a single unlucky entry date matters less. This effect is often called rupee-cost averaging. It also turns investing into a routine rather than a decision you re-make every month.\n\n"
                        "What it does not do: it does not guarantee a profit, it does not protect you if the whole market falls for a long time, and it does not make an unsuitable fund suitable.\n\n"
                        "You can usually pause or stop a SIP. Any exit load or tax rules depend on the scheme and are written in its documents.\n\n"
                        "Anyone describing a SIP as risk-free is describing it wrongly.",
            "example": "Suppose you invest ₹1,000 on the 5th of each month for three months.\n\n"
                       "Month 1: the unit price is ₹20, so you get 50 units.\n"
                       "Month 2: the price is ₹25, so you get 40 units.\n"
                       "Month 3: the price is ₹16, so you get 62.5 units.\n\n"
                       "You invested ₹3,000 and hold 152.5 units, an average cost of about ₹19.67 per unit, lower than the simple average of the three prices (₹20.33).\n\n"
                       "If the price later stays at ₹16, your units are worth ₹2,440, less than you put in. Averaging changes the cost; it does not remove the loss.",
            "analogy": "Think of buying rice for the household every month with the same budget. When rice is cheap, your money brings home more kilos; when it is costly, fewer.\n\n"
                       "Over a year you never paid only the highest price, and you never had to guess the best day to buy.\n\n"
                       "But if rice prices rise or fall for the whole year, your regular buying does not change that. A SIP works the same way.",
        },
        "hi": {
            "title": "एसआईपी क्या करता है, और क्या नहीं",
            "summary": "हर बार एक तय रकम लगाने से ख़रीद का भाव बँट जाता है। इससे जोखिम ख़त्म नहीं होता।",
            "simple": "एसआईपी (SIP) का मतलब है सिस्टमैटिक इन्वेस्टमेंट प्लान। आप तय समय पर, जैसे हर महीने, म्यूचुअल फंड में एक जैसी रकम लगाते हैं।\n\n"
                      "भाव कम हो तो आपके पैसे से ज़्यादा यूनिट मिलती हैं; भाव ज़्यादा हो तो कम। इससे आपकी ख़रीद का भाव बँट जाता है।\n\n"
                      "एसआईपी निवेश का एक तरीक़ा है, कोई उत्पाद नहीं। यह मुनाफ़े की गारंटी नहीं देता और नुकसान नहीं रोकता।",
            "detailed": "सिस्टमैटिक इन्वेस्टमेंट प्लान का मतलब है एक बार में सारा पैसा लगाने के बजाय नियमित अंतराल पर तय रकम लगाना। आम तौर पर यह बैंक खाते से अपने-आप कटने (ऑटो-डेबिट) के रूप में होता है।\n\n"
                        "यह क्या करता है: आपकी ख़रीद अलग-अलग भावों पर बँट जाती है, इसलिए किसी एक ग़लत दिन का असर कम होता है। इसे रुपी-कॉस्ट एवरेजिंग कहते हैं। साथ ही निवेश हर महीने का नया फ़ैसला न रहकर एक आदत बन जाता है।\n\n"
                        "यह क्या नहीं करता: मुनाफ़े की गारंटी नहीं देता, पूरा बाज़ार लंबे समय तक गिरे तो आपको नहीं बचाता, और किसी अनुपयुक्त फंड को उपयुक्त नहीं बनाता।\n\n"
                        "आम तौर पर एसआईपी रोकी या बंद की जा सकती है। एग्ज़िट लोड या टैक्स के नियम योजना पर निर्भर हैं और उसके दस्तावेज़ों में लिखे होते हैं।\n\n"
                        "जो कोई एसआईपी को बिना जोखिम का बताए, वह ग़लत बता रहा है।",
            "example": "मान लीजिए आप तीन महीने तक हर महीने की 5 तारीख़ को ₹1,000 लगाते हैं।\n\n"
                       "महीना 1: यूनिट का भाव ₹20 है, आपको 50 यूनिट मिलती हैं।\n"
                       "महीना 2: भाव ₹25 है, आपको 40 यूनिट मिलती हैं।\n"
                       "महीना 3: भाव ₹16 है, आपको 62.5 यूनिट मिलती हैं।\n\n"
                       "आपने ₹3,000 लगाए और आपके पास 152.5 यूनिट हैं, यानी औसत लागत लगभग ₹19.67 प्रति यूनिट, जो तीनों भावों के सीधे औसत (₹20.33) से कम है।\n\n"
                       "अगर बाद में भाव ₹16 पर ही रहे, तो आपकी यूनिट ₹2,440 की होंगी, यानी लगाए पैसे से कम। औसत से लागत बदलती है; नुकसान ख़त्म नहीं होता।",
            "analogy": "सोचिए आप हर महीने एक ही बजट में घर के लिए चावल ख़रीदते हैं। चावल सस्ता हो तो ज़्यादा किलो आते हैं; महँगा हो तो कम।\n\n"
                       "साल भर में आपने हमेशा सबसे ऊँचा दाम नहीं चुकाया, और सबसे अच्छा दिन चुनने का अंदाज़ा भी नहीं लगाना पड़ा।\n\n"
                       "लेकिन अगर पूरे साल चावल के दाम बढ़ते या घटते रहें, तो नियमित ख़रीद से यह नहीं बदलता। एसआईपी भी ऐसे ही काम करता है।",
        },
        "ta": {
            "title": "எஸ்ஐபி என்ன செய்யும், என்ன செய்யாது",
            "summary": "ஒவ்வொரு முறையும் ஒரே தொகையை முதலீடு செய்வதால் வாங்கும் விலை பரவுகிறது. ஆபத்து நீங்குவதில்லை.",
            "simple": "எஸ்ஐபி (SIP) என்றால் முறையான முதலீட்டுத் திட்டம். ஒரு மியூச்சுவல் ஃபண்டில் குறிப்பிட்ட நேரத்தில், உதாரணமாக மாதந்தோறும், ஒரே தொகையைப் போடுகிறீர்கள்.\n\n"
                      "விலை குறைவாக இருந்தால் உங்கள் பணத்துக்கு அதிக யூனிட்கள்; விலை அதிகமாக இருந்தால் குறைவான யூனிட்கள். இதனால் நீங்கள் கொடுக்கும் விலை பரவுகிறது.\n\n"
                      "எஸ்ஐபி ஒரு முதலீட்டு முறை, ஒரு தயாரிப்பு அல்ல. அது லாபத்தை உறுதி செய்யாது, நஷ்டத்தைத் தடுக்காது.",
            "detailed": "முறையான முதலீட்டுத் திட்டம் என்றால் மொத்தமாக ஒரே முறை போடாமல், சீரான இடைவெளியில் ஒரு நிலையான தொகையை முதலீடு செய்வது. பொதுவாக வங்கிக் கணக்கிலிருந்து தானாகப் பிடித்தம் (ஆட்டோ-டெபிட்) மூலம் நடக்கும்.\n\n"
                        "இது என்ன செய்யும்: உங்கள் வாங்குதல்கள் வெவ்வேறு விலைகளில் பரவுகின்றன, அதனால் ஒரு மோசமான நாளின் தாக்கம் குறைகிறது. இதை ரூபாய்-செலவு சராசரி என்பார்கள். முதலீடு ஒவ்வொரு மாதமும் புதிதாக எடுக்கும் முடிவாக இல்லாமல் பழக்கமாக மாறுகிறது.\n\n"
                        "இது என்ன செய்யாது: லாபத்தை உறுதி செய்யாது, முழுச் சந்தையும் நீண்ட காலம் சரிந்தால் உங்களைப் பாதுகாக்காது, பொருத்தமற்ற ஃபண்டைப் பொருத்தமானதாக மாற்றாது.\n\n"
                        "பொதுவாக எஸ்ஐபியை நிறுத்தி வைக்கலாம் அல்லது முடிக்கலாம். வெளியேறும் கட்டணம் (exit load), வரி விதிகள் திட்டத்தைப் பொறுத்தவை; அதன் ஆவணங்களில் எழுதியிருக்கும்.\n\n"
                        "எஸ்ஐபியை ஆபத்தில்லாதது என்று சொல்பவர் தவறாகச் சொல்கிறார்.",
            "example": "மூன்று மாதங்களுக்கு ஒவ்வொரு மாதமும் 5ஆம் தேதி ₹1,000 முதலீடு செய்கிறீர்கள் என்று வைத்துக்கொள்வோம்.\n\n"
                       "மாதம் 1: யூனிட் விலை ₹20, உங்களுக்கு 50 யூனிட்கள்.\n"
                       "மாதம் 2: விலை ₹25, உங்களுக்கு 40 யூனிட்கள்.\n"
                       "மாதம் 3: விலை ₹16, உங்களுக்கு 62.5 யூனிட்கள்.\n\n"
                       "நீங்கள் ₹3,000 போட்டீர்கள், 152.5 யூனிட்கள் வைத்திருக்கிறீர்கள். சராசரி செலவு யூனிட்டுக்கு சுமார் ₹19.67; இது மூன்று விலைகளின் நேரடி சராசரியான ₹20.33-ஐ விடக் குறைவு.\n\n"
                       "பிறகு விலை ₹16-லேயே இருந்தால், உங்கள் யூனிட்களின் மதிப்பு ₹2,440, போட்டதை விடக் குறைவு. சராசரி செலவை மாற்றும்; நஷ்டத்தை நீக்காது.",
            "analogy": "ஒவ்வொரு மாதமும் ஒரே பட்ஜெட்டில் வீட்டுக்கு அரிசி வாங்குவதை நினைத்துப் பாருங்கள். அரிசி மலிவாக இருந்தால் அதிக கிலோ வரும்; விலை அதிகமென்றால் குறைவாக.\n\n"
                       "ஒரு வருடத்தில் நீங்கள் எப்போதும் உச்ச விலையைக் கொடுக்கவில்லை; வாங்க சிறந்த நாளை ஊகிக்கவும் வேண்டியதில்லை.\n\n"
                       "ஆனால் வருடம் முழுவதும் அரிசி விலை ஏறிக்கொண்டோ இறங்கிக்கொண்டோ இருந்தால், சீராக வாங்குவது அதை மாற்றாது. எஸ்ஐபியும் அப்படித்தான்.",
        },
    },
    # ------------------------------------------------------------------
    "guaranteed-return-warning": {
        "resources": ["sebi_investor", "sachet", "cybercrime"],
        "en": {
            "title": "Why 'guaranteed returns' is a warning signal",
            "summary": "What guarantees legitimately exist, and why a high guaranteed figure is one of the strongest warning signals.",
            "simple": "The value of shares, funds and similar investments goes up and down. Nobody can guarantee it.\n\n"
                      "So if someone promises a high return that is \"guaranteed\" or \"fixed\", stop and check before doing anything.\n\n"
                      "Ask: who is promising this, are they registered, and where is it written down?",
            "detailed": "Market-linked returns cannot be guaranteed. The value of shares, bonds and funds changes, and nobody controls that.\n\n"
                        "Some regulated products do carry contractual commitments, for example bank fixed deposits and certain insurance or small savings products. These are modest, clearly documented and backed by an identifiable institution.\n\n"
                        "When a message promises a high guaranteed return, ask three questions:\n"
                        "1. Who exactly is legally bound by this promise, and are they registered with SEBI or RBI?\n"
                        "2. Where is the promise written down?\n"
                        "3. What happens to my money if the promise is not kept?\n\n"
                        "A guaranteed-return claim on its own does not prove fraud. It does mean the claim deserves checking before anything else, using official websites you type in yourself.",
            "example": "A message says: \"Earn 5% every week, guaranteed. Join our VIP group today.\"\n\n"
                       "5% a week adds up to more than 250% in a year, even without compounding. Regulated deposits typically pay single-digit interest a year.\n\n"
                       "That gap is the signal. A return that large would have to carry enormous risk, or not exist at all. Checking on SEBI's or RBI's website whether the sender is registered takes a few minutes and costs nothing.",
            "analogy": "Imagine a farmer telling you he can guarantee a double harvest every season, whatever the rain does. Experienced farmers know the weather decides a lot.\n\n"
                       "Someone who promises to control the weather is either mistaken or not being honest. Markets are like the weather here: nobody controls them, so nobody can honestly guarantee what they will deliver.",
        },
        "hi": {
            "title": "'गारंटीड रिटर्न' एक चेतावनी का संकेत क्यों है",
            "summary": "कौन सी गारंटी सच में होती हैं, और ऊँचे गारंटीड आँकड़े सबसे बड़े चेतावनी संकेतों में से एक क्यों हैं।",
            "simple": "शेयर, फंड और ऐसे निवेशों की कीमत ऊपर-नीचे होती है। इसकी गारंटी कोई नहीं दे सकता।\n\n"
                      "अगर कोई ऊँचे रिटर्न को \"गारंटीड\" या \"फ़िक्स्ड\" बताए, तो कुछ भी करने से पहले रुकिए और जाँचिए।\n\n"
                      "पूछिए: यह वादा कौन कर रहा है, क्या वह पंजीकृत है, और यह कहाँ लिखा है?",
            "detailed": "बाज़ार से जुड़े रिटर्न की गारंटी नहीं दी जा सकती। शेयर, बॉन्ड और फंड की कीमत बदलती है और उस पर किसी का नियंत्रण नहीं है।\n\n"
                        "कुछ विनियमित उत्पादों में अनुबंध के तहत वादा होता है, जैसे बैंक फ़िक्स्ड डिपॉज़िट और कुछ बीमा या छोटी बचत योजनाएँ। ये मामूली होते हैं, साफ़ लिखे होते हैं, और इनके पीछे एक पहचानी जा सकने वाली संस्था होती है।\n\n"
                        "जब कोई संदेश ऊँचे गारंटीड रिटर्न का वादा करे, तो तीन सवाल पूछिए:\n"
                        "1. यह वादा कानूनी रूप से किसका है, और क्या वह सेबी या आरबीआई में पंजीकृत है?\n"
                        "2. यह वादा कहाँ लिखा है?\n"
                        "3. वादा पूरा न हुआ तो मेरे पैसे का क्या होगा?\n\n"
                        "सिर्फ़ गारंटीड रिटर्न का दावा धोखाधड़ी साबित नहीं करता। पर इसका मतलब है कि सबसे पहले इसकी जाँच होनी चाहिए, उन आधिकारिक वेबसाइटों पर जिनका पता आप ख़ुद टाइप करें।",
            "example": "एक संदेश कहता है: \"हर हफ़्ते 5% कमाइए, गारंटीड। आज ही हमारे वीआईपी ग्रुप से जुड़िए।\"\n\n"
                       "हर हफ़्ते 5% का मतलब साल में 250% से भी ज़्यादा है, चक्रवृद्धि के बिना भी। विनियमित जमा योजनाएँ आम तौर पर साल में एक अंक (10% से कम) का ब्याज देती हैं।\n\n"
                       "यही फ़र्क़ संकेत है। इतना बड़ा रिटर्न या तो बहुत भारी जोखिम वाला होगा या असल में होगा ही नहीं। भेजने वाला पंजीकृत है या नहीं, यह सेबी या आरबीआई की वेबसाइट पर जाँचने में कुछ मिनट लगते हैं और कोई ख़र्च नहीं।",
            "analogy": "सोचिए एक किसान कहे कि वह हर मौसम में दोगुनी फ़सल की गारंटी देता है, बारिश चाहे जैसी हो। अनुभवी किसान जानते हैं कि मौसम बहुत कुछ तय करता है।\n\n"
                       "जो मौसम पर क़ाबू का वादा करे, वह या तो ग़लत है या ईमानदार नहीं। बाज़ार भी मौसम जैसा है: उस पर किसी का क़ाबू नहीं, इसलिए कोई ईमानदारी से उसके नतीजे की गारंटी नहीं दे सकता।",
        },
        "ta": {
            "title": "'உறுதியான வருமானம்' ஏன் ஒரு எச்சரிக்கை அறிகுறி",
            "summary": "உண்மையில் எந்த உத்தரவாதங்கள் உள்ளன, அதிக உறுதியான வருமானம் ஏன் வலுவான எச்சரிக்கை அறிகுறிகளில் ஒன்று.",
            "simple": "பங்குகள், ஃபண்டுகள் போன்ற முதலீடுகளின் மதிப்பு ஏறி இறங்கும். அதை யாராலும் உறுதி செய்ய முடியாது.\n\n"
                      "யாராவது அதிக வருமானத்தை \"உறுதி\" அல்லது \"நிலையானது\" என்று சொன்னால், எதுவும் செய்வதற்கு முன் நிறுத்தி சரிபாருங்கள்.\n\n"
                      "கேளுங்கள்: இந்த வாக்குறுதியைத் தருவது யார், அவர்கள் பதிவு பெற்றவர்களா, இது எங்கே எழுதப்பட்டுள்ளது?",
            "detailed": "சந்தையுடன் இணைந்த வருமானத்தை உறுதி செய்ய முடியாது. பங்குகள், பத்திரங்கள், ஃபண்டுகளின் மதிப்பு மாறுகிறது; அதை யாரும் கட்டுப்படுத்துவதில்லை.\n\n"
                        "சில ஒழுங்குபடுத்தப்பட்ட தயாரிப்புகளில் ஒப்பந்த அடிப்படையிலான உறுதி உண்டு, உதாரணமாக வங்கி நிலை வைப்புகள், சில காப்பீடு அல்லது சிறு சேமிப்புத் திட்டங்கள். இவை மிதமானவை, தெளிவாக எழுதப்பட்டவை, அடையாளம் காணக்கூடிய நிறுவனத்தின் ஆதரவு கொண்டவை.\n\n"
                        "ஒரு செய்தி அதிக உறுதியான வருமானத்தை வாக்களித்தால், மூன்று கேள்விகள் கேளுங்கள்:\n"
                        "1. இந்த வாக்குறுதிக்கு சட்டப்படி பொறுப்பானவர் யார், அவர் செபி அல்லது ஆர்பிஐயில் பதிவு பெற்றவரா?\n"
                        "2. இந்த வாக்குறுதி எங்கே எழுதப்பட்டுள்ளது?\n"
                        "3. வாக்குறுதி நிறைவேறாவிட்டால் என் பணத்துக்கு என்ன ஆகும்?\n\n"
                        "உறுதியான வருமானம் என்ற கூற்று மட்டுமே மோசடியை நிரூபிக்காது. ஆனால் அதை முதலில் சரிபார்க்க வேண்டும், நீங்களே முகவரியைத் தட்டச்சு செய்யும் அதிகாரப்பூர்வ இணையதளங்களில்.",
            "example": "ஒரு செய்தி சொல்கிறது: \"ஒவ்வொரு வாரமும் 5% சம்பாதியுங்கள், உறுதி. இன்றே எங்கள் விஐபி குழுவில் சேருங்கள்.\"\n\n"
                       "வாரம் 5% என்றால் வருடத்துக்கு 250%-க்கு மேல், கூட்டு வட்டி இல்லாமலே. ஒழுங்குபடுத்தப்பட்ட வைப்புகள் பொதுவாக வருடத்துக்கு ஒற்றை இலக்க (10%-க்குக் குறைவான) வட்டி தருகின்றன.\n\n"
                       "இந்த இடைவெளிதான் அறிகுறி. அவ்வளவு பெரிய வருமானம் மிகப் பெரிய ஆபத்துடன் இருக்க வேண்டும், அல்லது உண்மையில் இல்லாமலே இருக்கும். அனுப்பியவர் பதிவு பெற்றவரா என்று செபி அல்லது ஆர்பிஐ இணையதளத்தில் பார்க்க சில நிமிடங்களே ஆகும், செலவும் இல்லை.",
            "analogy": "மழை எப்படி இருந்தாலும் ஒவ்வொரு பருவத்திலும் இரட்டை அறுவடைக்கு உத்தரவாதம் தருவதாக ஒரு விவசாயி சொல்வதாக நினைத்துப் பாருங்கள். அனுபவமுள்ள விவசாயிகளுக்குத் தெரியும், வானிலைதான் பலவற்றைத் தீர்மானிக்கிறது.\n\n"
                       "வானிலையைக் கட்டுப்படுத்துவதாகச் சொல்பவர் தவறாக நினைக்கிறார் அல்லது நேர்மையாக இல்லை. சந்தையும் வானிலை போலத்தான்: யாரும் அதைக் கட்டுப்படுத்துவதில்லை, எனவே அதன் விளைவை நேர்மையாக யாரும் உறுதி செய்ய முடியாது.",
        },
    },
    # ------------------------------------------------------------------
    "never-share-otp": {
        "resources": ["cybercrime", "rbi_kehta_hai", "rbi_cms"],
        "en": {
            "title": "UPI, OTP and PIN safety",
            "summary": "What an OTP and UPI PIN actually authorise, and what to do if you have already shared one.",
            "simple": "An OTP or UPI PIN is like a key to your money. If you give it to someone, they can take your money.\n\n"
                      "You enter your UPI PIN only to send money, never to receive it. No honest bank, company or official will ever ask you for an OTP, PIN or password.\n\n"
                      "If you already shared one, call your bank right away and report it on 1930.",
            "detailed": "An OTP (one-time password) authorises one specific action: a payment, a login or a change of details. Sharing it lets someone else complete that action in your name.\n\n"
                        "Your UPI PIN is needed only to send money or approve a payment. Receiving money never needs your PIN, never needs you to scan a QR code, and never needs you to approve a \"collect request\". If a screen asks for your PIN to \"receive\" money, it is a payment going out.\n\n"
                        "No bank, broker, regulator, government office or delivery company will ask you for an OTP, PIN, password or card CVV, by phone, message or email.\n\n"
                        "If you have already shared one:\n"
                        "1. Call your bank on the number printed on your card or passbook and ask them to block the card or UPI and check recent transactions.\n"
                        "2. Report it at cybercrime.gov.in or on the 1930 helpline. Reporting early matters.\n"
                        "3. Keep the messages, phone numbers and transaction references.\n\n"
                        "Being targeted is not your fault. Acting quickly matters more than feeling embarrassed.",
            "example": "You are selling an old cupboard online. A \"buyer\" says they will pay ₹5,000 and sends a UPI request. Your app shows: \"Enter UPI PIN to pay ₹5,000\".\n\n"
                       "This is not a payment to you; it is a request for you to pay them. Entering your PIN would send ₹5,000 out of your account.\n\n"
                       "A real buyer can simply send money to your UPI ID. You do nothing except check your account afterwards.",
            "analogy": "Think of your UPI PIN as the key to your house. You use it to open the door from the inside when you choose to let something out.\n\n"
                       "Someone who wants to deliver a parcel does not need your key; they just hand it over. If a \"delivery person\" insists on borrowing your key first, the parcel is not the real reason they came.",
        },
        "hi": {
            "title": "यूपीआई, ओटीपी और पिन की सुरक्षा",
            "summary": "ओटीपी और यूपीआई पिन असल में किस बात की अनुमति देते हैं, और अगर आपने किसी को बता दिया हो तो क्या करें।",
            "simple": "ओटीपी या यूपीआई पिन आपके पैसे की चाबी जैसा है। किसी को दे दिया तो वह आपका पैसा ले सकता है।\n\n"
                      "यूपीआई पिन सिर्फ़ पैसा भेजने के लिए डाला जाता है, पाने के लिए कभी नहीं। कोई भी ईमानदार बैंक, कंपनी या अधिकारी आपसे ओटीपी, पिन या पासवर्ड नहीं माँगेगा।\n\n"
                      "अगर आप बता चुके हैं, तो तुरंत अपने बैंक को फ़ोन करें और 1930 पर शिकायत करें।",
            "detailed": "ओटीपी (वन-टाइम पासवर्ड) किसी एक काम की अनुमति देता है: भुगतान, लॉगिन या जानकारी बदलना। इसे बताने से कोई और आपके नाम से वह काम कर सकता है।\n\n"
                        "यूपीआई पिन सिर्फ़ पैसा भेजने या भुगतान मंज़ूर करने के लिए चाहिए। पैसा पाने के लिए न पिन चाहिए, न क्यूआर कोड स्कैन करना, न कोई \"कलेक्ट रिक्वेस्ट\" मंज़ूर करना। अगर कोई स्क्रीन पैसा \"पाने\" के लिए पिन माँगे, तो असल में पैसा बाहर जा रहा है।\n\n"
                        "कोई बैंक, ब्रोकर, नियामक, सरकारी दफ़्तर या डिलीवरी कंपनी आपसे फ़ोन, मैसेज या ईमेल पर ओटीपी, पिन, पासवर्ड या कार्ड का सीवीवी नहीं माँगेगी।\n\n"
                        "अगर आप बता चुके हैं:\n"
                        "1. कार्ड या पासबुक पर छपे नंबर पर अपने बैंक को फ़ोन करें, कार्ड या यूपीआई बंद करवाएँ और हाल के लेन-देन जँचवाएँ।\n"
                        "2. cybercrime.gov.in पर या 1930 हेल्पलाइन पर शिकायत करें। जल्दी शिकायत करना ज़रूरी है।\n"
                        "3. मैसेज, फ़ोन नंबर और लेन-देन के रेफ़रेंस संभालकर रखें।\n\n"
                        "निशाना बनना आपकी ग़लती नहीं है। शर्मिंदा होने से ज़्यादा ज़रूरी है जल्दी कदम उठाना।",
            "example": "आप ऑनलाइन एक पुरानी अलमारी बेच रहे हैं। एक \"ख़रीदार\" कहता है कि वह ₹5,000 देगा और यूपीआई रिक्वेस्ट भेजता है। आपके ऐप में दिखता है: \"₹5,000 भुगतान के लिए यूपीआई पिन डालें\"।\n\n"
                       "यह आपको भुगतान नहीं है; यह आपसे उसे भुगतान करने की माँग है। पिन डालते ही आपके खाते से ₹5,000 चले जाएँगे।\n\n"
                       "असली ख़रीदार सीधे आपकी यूपीआई आईडी पर पैसा भेज सकता है। आपको बाद में सिर्फ़ खाता देखना होता है।",
            "analogy": "अपने यूपीआई पिन को घर की चाबी समझिए। आप इसे तब इस्तेमाल करते हैं जब आप ख़ुद कुछ बाहर भेजना चाहें।\n\n"
                       "जो पार्सल देने आया है उसे आपकी चाबी की ज़रूरत नहीं; वह बस पार्सल थमा देता है। अगर कोई \"डिलीवरी वाला\" पहले आपकी चाबी माँगने पर अड़ जाए, तो वह पार्सल देने नहीं आया।",
        },
        "ta": {
            "title": "யுபிஐ, ஓடிபி, பின் பாதுகாப்பு",
            "summary": "ஓடிபி, யுபிஐ பின் உண்மையில் எதற்கு அனுமதி தருகின்றன, ஏற்கனவே பகிர்ந்திருந்தால் என்ன செய்வது.",
            "simple": "ஓடிபி அல்லது யுபிஐ பின் உங்கள் பணத்தின் சாவி போன்றது. அதை யாரிடமாவது கொடுத்தால் அவர்கள் உங்கள் பணத்தை எடுக்க முடியும்.\n\n"
                      "யுபிஐ பின்னை பணம் அனுப்ப மட்டுமே போடுவீர்கள், பணம் பெற ஒருபோதும் இல்லை. நேர்மையான எந்த வங்கியும் நிறுவனமும் அதிகாரியும் உங்களிடம் ஓடிபி, பின், கடவுச்சொல் கேட்க மாட்டார்கள்.\n\n"
                      "ஏற்கனவே பகிர்ந்திருந்தால், உடனே உங்கள் வங்கியை அழைத்து 1930-இல் புகார் அளியுங்கள்.",
            "detailed": "ஓடிபி (ஒருமுறை கடவுச்சொல்) ஒரு குறிப்பிட்ட செயலுக்கு அனுமதி தருகிறது: பணம் செலுத்துதல், உள்நுழைதல் அல்லது விவரங்களை மாற்றுதல். அதைப் பகிர்ந்தால் வேறொருவர் உங்கள் பெயரில் அந்தச் செயலை முடிக்க முடியும்.\n\n"
                        "யுபிஐ பின் பணம் அனுப்ப அல்லது கட்டணத்தை அங்கீகரிக்க மட்டுமே தேவை. பணம் பெற பின் தேவையில்லை, க்யூஆர் குறியீட்டை ஸ்கேன் செய்யத் தேவையில்லை, \"கலெக்ட் ரிக்வெஸ்ட்\" ஏற்கத் தேவையில்லை. பணம் \"பெற\" ஒரு திரை பின் கேட்டால், உண்மையில் பணம் வெளியே போகிறது.\n\n"
                        "எந்த வங்கியும், தரகரும், ஒழுங்குமுறை அமைப்பும், அரசு அலுவலகமும், டெலிவரி நிறுவனமும் தொலைபேசி, செய்தி அல்லது மின்னஞ்சலில் ஓடிபி, பின், கடவுச்சொல் அல்லது கார்டு சிவிவி கேட்காது.\n\n"
                        "ஏற்கனவே பகிர்ந்திருந்தால்:\n"
                        "1. உங்கள் கார்டு அல்லது பாஸ்புக்கில் அச்சிடப்பட்ட எண்ணில் வங்கியை அழைத்து, கார்டு அல்லது யுபிஐயை முடக்கி, சமீபத்திய பரிவர்த்தனைகளைச் சரிபார்க்கச் சொல்லுங்கள்.\n"
                        "2. cybercrime.gov.in-இல் அல்லது 1930 உதவி எண்ணில் புகார் அளியுங்கள். சீக்கிரம் புகார் அளிப்பது முக்கியம்.\n"
                        "3. செய்திகள், தொலைபேசி எண்கள், பரிவர்த்தனை குறிப்புகளை வைத்திருங்கள்.\n\n"
                        "குறிவைக்கப்படுவது உங்கள் தவறு அல்ல. வெட்கப்படுவதை விட வேகமாகச் செயல்படுவதே முக்கியம்.",
            "example": "நீங்கள் ஒரு பழைய அலமாரியை ஆன்லைனில் விற்கிறீர்கள். ஒரு \"வாங்குபவர்\" ₹5,000 தருவதாகச் சொல்லி யுபிஐ கோரிக்கை அனுப்புகிறார். உங்கள் செயலியில் தெரிகிறது: \"₹5,000 செலுத்த யுபிஐ பின்னை உள்ளிடவும்\".\n\n"
                       "இது உங்களுக்கு வரும் பணம் அல்ல; நீங்கள் அவருக்குப் பணம் செலுத்தச் சொல்லும் கோரிக்கை. பின்னை உள்ளிட்டால் உங்கள் கணக்கிலிருந்து ₹5,000 போய்விடும்.\n\n"
                       "உண்மையான வாங்குபவர் உங்கள் யுபிஐ ஐடிக்கு நேரடியாகப் பணம் அனுப்பலாம். நீங்கள் பிறகு கணக்கைப் பார்த்தால் போதும்.",
            "analogy": "உங்கள் யுபிஐ பின்னை வீட்டுச் சாவியாக நினையுங்கள். நீங்களே எதையாவது வெளியே அனுப்ப விரும்பும்போது மட்டும் அதைப் பயன்படுத்துகிறீர்கள்.\n\n"
                       "பார்சல் கொடுக்க வந்தவருக்கு உங்கள் சாவி தேவையில்லை; அவர் பார்சலைக் கையில் கொடுத்தால் போதும். ஒரு \"டெலிவரி நபர்\" முதலில் சாவியைக் கேட்டு வற்புறுத்தினால், அவர் பார்சலுக்காக வரவில்லை.",
        },
    },
    # ------------------------------------------------------------------
    "investor-rights-india": {
        "resources": ["scores", "sebi", "rbi_cms"],
        "en": {
            "title": "Your rights as an investor",
            "summary": "What you are entitled to ask for, and the escalation path when a firm does not resolve your complaint.",
            "simple": "You have the right to clear, written information before you invest, including costs and risks.\n\n"
                      "You can check whether a firm or adviser is registered with SEBI, for free, on SEBI's website.\n\n"
                      "If a registered firm does not solve your complaint, you can take it to SEBI's SCORES portal. You can always say no and take your time.",
            "detailed": "As an investor in India you are entitled to:\n"
                        "- Clear, written information about what you are offered, including all costs and risks.\n"
                        "- Deal with registered intermediaries. Registration is public and you can look it up on sebi.gov.in yourself.\n"
                        "- A documented grievance process at the firm, with timelines.\n"
                        "- Escalate to SEBI's SCORES portal if a SEBI-registered firm does not resolve your complaint, and beyond that to the market's online dispute resolution process.\n"
                        "- Say no, take your time, and ask for everything in writing.\n\n"
                        "For banks the path is similar: complain to the bank first; if it does not reply within 30 days or you are not satisfied, you can complain to the RBI Ombudsman through cms.rbi.org.in.\n\n"
                        "The most useful habit is verifying registration independently: type the regulator's address yourself and search for the firm or person. Never rely on a link you were sent, however official it looks.",
            "example": "Meena's broker has not credited money from a sale to her bank account for two weeks. Calls go unanswered.\n\n"
                       "She first writes to the broker's grievance email, keeping a copy. When the broker does not resolve it, she registers on scores.sebi.gov.in, files a complaint with the details and documents, and notes the complaint number to track it.\n\n"
                       "Throughout, she uses only official addresses she typed herself, and never shares her OTP or password with anyone claiming to \"speed it up\".",
            "analogy": "Think of buying from a licensed shop in a market. If a product is faulty, you go to the shop first. If the shop ignores you, the market association, which licensed the shop, has a counter for complaints.\n\n"
                       "That counter works only for licensed shops. A roadside seller with no licence cannot be brought there, which is why checking the licence before you buy matters so much.",
        },
        "hi": {
            "title": "निवेशक के रूप में आपके अधिकार",
            "summary": "आप क्या माँग सकते हैं, और कंपनी शिकायत हल न करे तो आगे कहाँ जाएँ।",
            "simple": "निवेश से पहले आपको साफ़, लिखित जानकारी पाने का अधिकार है, जिसमें ख़र्च और जोखिम शामिल हैं।\n\n"
                      "कोई कंपनी या सलाहकार सेबी में पंजीकृत है या नहीं, यह आप सेबी की वेबसाइट पर मुफ़्त में देख सकते हैं।\n\n"
                      "अगर पंजीकृत कंपनी आपकी शिकायत हल न करे, तो आप सेबी के स्कोर्स (SCORES) पोर्टल पर जा सकते हैं। आप हमेशा मना कर सकते हैं और समय ले सकते हैं।",
            "detailed": "भारत में निवेशक के रूप में आपके अधिकार:\n"
                        "- जो पेश किया जा रहा है उसकी साफ़, लिखित जानकारी, सारे ख़र्च और जोखिम समेत।\n"
                        "- सिर्फ़ पंजीकृत मध्यस्थों से लेन-देन। पंजीकरण सार्वजनिक है और आप ख़ुद sebi.gov.in पर देख सकते हैं।\n"
                        "- कंपनी में तय समय-सीमा वाली लिखित शिकायत प्रक्रिया।\n"
                        "- अगर सेबी-पंजीकृत कंपनी शिकायत हल न करे तो सेबी के स्कोर्स पोर्टल पर, और उसके आगे बाज़ार की ऑनलाइन विवाद निपटान प्रक्रिया तक जाना।\n"
                        "- मना करना, समय लेना, और सब कुछ लिखित में माँगना।\n\n"
                        "बैंकों के लिए रास्ता मिलता-जुलता है: पहले बैंक से शिकायत करें; अगर 30 दिन में जवाब न मिले या आप संतुष्ट न हों, तो cms.rbi.org.in पर आरबीआई लोकपाल को शिकायत कर सकते हैं।\n\n"
                        "सबसे काम की आदत है पंजीकरण की ख़ुद जाँच करना: नियामक का पता ख़ुद टाइप करें और कंपनी या व्यक्ति को खोजें। भेजे गए किसी लिंक पर भरोसा न करें, चाहे वह कितना भी आधिकारिक दिखे।",
            "example": "मीना के ब्रोकर ने दो हफ़्ते से शेयर बिक्री का पैसा उसके बैंक खाते में नहीं डाला है। फ़ोन का जवाब नहीं मिलता।\n\n"
                       "वह पहले ब्रोकर के शिकायत ईमेल पर लिखती है और उसकी प्रति रखती है। जब ब्रोकर हल नहीं करता, तो वह scores.sebi.gov.in पर पंजीकरण करती है, ब्योरे और दस्तावेज़ के साथ शिकायत दर्ज करती है, और स्थिति देखने के लिए शिकायत नंबर लिख लेती है।\n\n"
                       "पूरे समय वह सिर्फ़ ख़ुद टाइप किए आधिकारिक पते इस्तेमाल करती है, और \"जल्दी करवाने\" का दावा करने वाले किसी को भी अपना ओटीपी या पासवर्ड नहीं बताती।",
            "analogy": "सोचिए आप बाज़ार की एक लाइसेंस वाली दुकान से सामान ख़रीदते हैं। सामान ख़राब निकले तो पहले दुकान पर जाते हैं। दुकान अनसुना करे, तो बाज़ार संघ, जिसने दुकान को लाइसेंस दिया, उसकी शिकायत खिड़की होती है।\n\n"
                       "वह खिड़की सिर्फ़ लाइसेंस वाली दुकानों के लिए है। बिना लाइसेंस वाले सड़क के विक्रेता को वहाँ नहीं लाया जा सकता, इसीलिए ख़रीदने से पहले लाइसेंस देखना इतना ज़रूरी है।",
        },
        "ta": {
            "title": "முதலீட்டாளராக உங்கள் உரிமைகள்",
            "summary": "நீங்கள் எதைக் கேட்க உரிமை உண்டு, ஒரு நிறுவனம் புகாரைத் தீர்க்காவிட்டால் அடுத்து எங்கே செல்வது.",
            "simple": "முதலீடு செய்வதற்கு முன் செலவுகள், ஆபத்துகள் உட்பட தெளிவான, எழுத்துப்பூர்வ தகவலைப் பெற உங்களுக்கு உரிமை உண்டு.\n\n"
                      "ஒரு நிறுவனம் அல்லது ஆலோசகர் செபியில் பதிவு பெற்றவரா என்பதை செபி இணையதளத்தில் இலவசமாகப் பார்க்கலாம்.\n\n"
                      "பதிவு பெற்ற நிறுவனம் உங்கள் புகாரைத் தீர்க்காவிட்டால், செபியின் ஸ்கோர்ஸ் (SCORES) தளத்துக்குக் கொண்டு செல்லலாம். நீங்கள் எப்போதும் மறுக்கலாம், நேரம் எடுத்துக்கொள்ளலாம்.",
            "detailed": "இந்தியாவில் முதலீட்டாளராக உங்கள் உரிமைகள்:\n"
                        "- உங்களுக்கு வழங்கப்படுவது பற்றி அனைத்துச் செலவுகள், ஆபத்துகள் உட்பட தெளிவான எழுத்துப்பூர்வ தகவல்.\n"
                        "- பதிவு பெற்ற இடைத்தரகர்களுடன் மட்டும் பரிவர்த்தனை. பதிவு பொதுவானது; sebi.gov.in-இல் நீங்களே பார்க்கலாம்.\n"
                        "- நிறுவனத்தில் காலக்கெடுவுடன் கூடிய எழுத்துப்பூர்வ புகார் நடைமுறை.\n"
                        "- செபியில் பதிவு பெற்ற நிறுவனம் புகாரைத் தீர்க்காவிட்டால் செபியின் ஸ்கோர்ஸ் தளத்துக்கும், அதற்கு மேல் சந்தையின் ஆன்லைன் தகராறு தீர்வு நடைமுறைக்கும் செல்லுதல்.\n"
                        "- மறுக்க, நேரம் எடுத்துக்கொள்ள, அனைத்தையும் எழுத்தில் கேட்க.\n\n"
                        "வங்கிகளுக்கும் இதே போன்ற வழி: முதலில் வங்கியிடம் புகார் அளியுங்கள்; 30 நாட்களுக்குள் பதில் இல்லையென்றால் அல்லது திருப்தி இல்லையென்றால், cms.rbi.org.in மூலம் ஆர்பிஐ குறைதீர்ப்பாளரிடம் புகார் அளிக்கலாம்.\n\n"
                        "மிகப் பயனுள்ள பழக்கம், பதிவை நீங்களே சரிபார்ப்பது: ஒழுங்குமுறை அமைப்பின் முகவரியை நீங்களே தட்டச்சு செய்து நிறுவனத்தையோ நபரையோ தேடுங்கள். உங்களுக்கு அனுப்பப்பட்ட இணைப்பை, எவ்வளவு அதிகாரப்பூர்வமாகத் தெரிந்தாலும், நம்பாதீர்கள்.",
            "example": "மீனாவின் தரகர் இரண்டு வாரங்களாக பங்கு விற்ற பணத்தை அவரது வங்கிக் கணக்கில் வரவு வைக்கவில்லை. அழைப்புகளுக்குப் பதில் இல்லை.\n\n"
                       "அவர் முதலில் தரகரின் புகார் மின்னஞ்சலுக்கு எழுதி, நகலை வைத்துக்கொள்கிறார். தரகர் தீர்க்காதபோது, scores.sebi.gov.in-இல் பதிவு செய்து, விவரங்கள், ஆவணங்களுடன் புகார் அளித்து, நிலையைப் பார்க்க புகார் எண்ணைக் குறித்துக்கொள்கிறார்.\n\n"
                       "முழுவதும் அவர் தானே தட்டச்சு செய்த அதிகாரப்பூர்வ முகவரிகளை மட்டுமே பயன்படுத்துகிறார்; \"வேகமாக்கித் தருகிறேன்\" என்று சொல்லும் யாரிடமும் ஓடிபி அல்லது கடவுச்சொல்லைப் பகிர்வதில்லை.",
            "analogy": "சந்தையில் உரிமம் பெற்ற ஒரு கடையில் பொருள் வாங்குவதை நினைத்துப் பாருங்கள். பொருள் குறைபாடுடையதாக இருந்தால் முதலில் கடைக்குச் செல்வீர்கள். கடை கண்டுகொள்ளாவிட்டால், கடைக்கு உரிமம் தந்த சந்தைச் சங்கத்திடம் புகார் சாளரம் இருக்கிறது.\n\n"
                       "அந்தச் சாளரம் உரிமம் பெற்ற கடைகளுக்கு மட்டுமே. உரிமம் இல்லாத சாலையோர விற்பனையாளரை அங்கே கொண்டு வர முடியாது; அதனால்தான் வாங்குவதற்கு முன் உரிமத்தைப் பார்ப்பது மிக முக்கியம்.",
        },
    },
    # ------------------------------------------------------------------
    "what-is-volatility": {
        "resources": ["sebi_investor", "ncfe"],
        "en": {
            "title": "What volatility means",
            "summary": "A measure of how much a price has moved, not of which direction it will move next.",
            "simple": "Volatility means how much a price jumps up and down.\n\n"
                      "A price that moves a little each day has low volatility. A price that swings a lot has high volatility.\n\n"
                      "Volatility tells you about past movement. It does not tell you whether the price will go up or down next.",
            "detailed": "Volatility describes how much a price has moved up and down over a period. It measures variability, not direction.\n\n"
                        "At a high level, it is calculated from how widely past price changes were spread around their average. A wider spread gives a higher figure.\n\n"
                        "What it can teach you:\n"
                        "- Prices can fluctuate a lot over short periods.\n"
                        "- A higher figure means larger past swings, in both directions.\n"
                        "- Two investments with a similar average return can feel completely different to hold.\n\n"
                        "Limitations: it is entirely backward-looking. A calm past period does not guarantee a calm future one, and volatility says nothing about whether a price will rise or fall. Money you may need soon is more exposed to short-term swings than money you can leave for a long time.",
            "example": "Two made-up investments both start at ₹100 and both end the month at ₹103.\n\n"
                       "Investment A goes ₹100 → ₹101 → ₹102 → ₹103. Small, steady moves: low volatility.\n"
                       "Investment B goes ₹100 → ₹115 → ₹88 → ₹103. Large swings: high volatility.\n\n"
                       "The ending value is the same, but someone who needed money in the middle of the month would have got ₹88 from B. That is what volatility describes.",
            "analogy": "Think of two bus journeys that both take one hour. One is on a smooth highway; the other is on a bumpy village road.\n\n"
                       "You arrive at the same time, but the second ride shakes you around much more, and if you had to get off midway, where you would be standing is far less predictable.\n\n"
                       "Volatility measures the bumps, not the destination.",
        },
        "hi": {
            "title": "उतार-चढ़ाव (वोलैटिलिटी) का मतलब",
            "summary": "यह बताता है कि कीमत कितनी हिली है, यह नहीं कि आगे किस दिशा में जाएगी।",
            "simple": "वोलैटिलिटी यानी कीमत कितना ऊपर-नीचे होती है।\n\n"
                      "जो कीमत रोज़ थोड़ा-थोड़ा बदले, उसमें उतार-चढ़ाव कम है। जो बहुत झूले, उसमें ज़्यादा।\n\n"
                      "वोलैटिलिटी पिछली हलचल बताती है। यह नहीं बताती कि आगे कीमत बढ़ेगी या घटेगी।",
            "detailed": "वोलैटिलिटी बताती है कि किसी अवधि में कीमत कितनी ऊपर-नीचे हुई। यह बदलाव की मात्रा मापती है, दिशा नहीं।\n\n"
                        "मोटे तौर पर, यह इससे निकाली जाती है कि पिछले बदलाव अपने औसत से कितने फैले हुए थे। ज़्यादा फैलाव तो ज़्यादा आँकड़ा।\n\n"
                        "इससे क्या सीख मिलती है:\n"
                        "- कम समय में भी कीमतें काफ़ी बदल सकती हैं।\n"
                        "- ऊँचे आँकड़े का मतलब है पहले बड़े झूले, दोनों दिशाओं में।\n"
                        "- एक जैसे औसत रिटर्न वाले दो निवेश रखने में बिल्कुल अलग महसूस हो सकते हैं।\n\n"
                        "सीमाएँ: यह पूरी तरह पीछे देखती है। पहले शांत रहना आगे शांत रहने की गारंटी नहीं है, और वोलैटिलिटी यह नहीं बताती कि कीमत बढ़ेगी या घटेगी। जिस पैसे की जल्दी ज़रूरत हो सकती है, उस पर कम समय के झूलों का असर ज़्यादा पड़ता है।",
            "example": "दो काल्पनिक निवेश ₹100 से शुरू होते हैं और महीने के अंत में दोनों ₹103 पर हैं।\n\n"
                       "निवेश A: ₹100 → ₹101 → ₹102 → ₹103। छोटे, सधे बदलाव: कम उतार-चढ़ाव।\n"
                       "निवेश B: ₹100 → ₹115 → ₹88 → ₹103। बड़े झूले: ज़्यादा उतार-चढ़ाव।\n\n"
                       "आख़िरी कीमत एक जैसी है, पर जिसे महीने के बीच में पैसा चाहिए होता, उसे B से ₹88 मिलते। वोलैटिलिटी यही बताती है।",
            "analogy": "सोचिए दो बस यात्राएँ, दोनों एक घंटे की। एक चिकने हाईवे पर है, दूसरी ऊबड़-खाबड़ गाँव की सड़क पर।\n\n"
                       "आप एक ही समय पहुँचते हैं, पर दूसरी यात्रा में आप बहुत ज़्यादा हिलते हैं, और अगर बीच में उतरना पड़े तो आप कहाँ होंगे, इसका अंदाज़ा लगाना कहीं ज़्यादा मुश्किल है।\n\n"
                       "वोलैटिलिटी झटकों को मापती है, मंज़िल को नहीं।",
        },
        "ta": {
            "title": "ஏற்ற இறக்கம் (வோலாட்டிலிட்டி) என்றால் என்ன",
            "summary": "ஒரு விலை எவ்வளவு அசைந்தது என்பதன் அளவு; அடுத்து எந்தத் திசையில் போகும் என்பதல்ல.",
            "simple": "வோலாட்டிலிட்டி என்றால் ஒரு விலை எவ்வளவு ஏறி இறங்குகிறது என்பது.\n\n"
                      "ஒவ்வொரு நாளும் கொஞ்சமாக மாறும் விலைக்கு ஏற்ற இறக்கம் குறைவு. அதிகமாக ஆடும் விலைக்கு அதிகம்.\n\n"
                      "வோலாட்டிலிட்டி கடந்த கால அசைவைச் சொல்கிறது. அடுத்து விலை ஏறுமா இறங்குமா என்று சொல்லாது.",
            "detailed": "ஒரு காலகட்டத்தில் விலை எவ்வளவு ஏறி இறங்கியது என்பதை வோலாட்டிலிட்டி விவரிக்கிறது. இது மாற்றத்தின் அளவை அளக்கிறது, திசையை அல்ல.\n\n"
                        "சுருக்கமாக, கடந்த கால விலை மாற்றங்கள் அவற்றின் சராசரியைச் சுற்றி எவ்வளவு பரவியிருந்தன என்பதிலிருந்து கணக்கிடப்படுகிறது. அதிக பரவல் என்றால் அதிக எண்.\n\n"
                        "இது கற்றுத் தருவது:\n"
                        "- குறுகிய காலத்திலும் விலைகள் நிறைய மாறலாம்.\n"
                        "- அதிக எண் என்றால் கடந்த காலத்தில் இரு திசைகளிலும் பெரிய ஆட்டம்.\n"
                        "- ஒரே மாதிரியான சராசரி வருமானம் கொண்ட இரண்டு முதலீடுகள் வைத்திருக்கும்போது முற்றிலும் வேறாக உணரப்படலாம்.\n\n"
                        "வரம்புகள்: இது முழுக்க பின்னோக்கிப் பார்க்கிறது. கடந்த காலம் அமைதியாக இருந்தது என்பது எதிர்காலம் அமைதியாக இருக்கும் என்பதற்கு உத்தரவாதம் அல்ல; விலை ஏறுமா இறங்குமா என்று வோலாட்டிலிட்டி சொல்லாது. விரைவில் தேவைப்படக்கூடிய பணம் குறுகிய கால ஆட்டங்களால் அதிகம் பாதிக்கப்படும்.",
            "example": "இரண்டு கற்பனை முதலீடுகள் ₹100-இல் தொடங்கி, மாத இறுதியில் இரண்டும் ₹103-இல் உள்ளன.\n\n"
                       "முதலீடு A: ₹100 → ₹101 → ₹102 → ₹103. சிறிய, சீரான மாற்றங்கள்: குறைந்த ஏற்ற இறக்கம்.\n"
                       "முதலீடு B: ₹100 → ₹115 → ₹88 → ₹103. பெரிய ஆட்டங்கள்: அதிக ஏற்ற இறக்கம்.\n\n"
                       "இறுதி மதிப்பு ஒன்றுதான், ஆனால் மாதத்தின் நடுவில் பணம் தேவைப்பட்டவருக்கு B-இலிருந்து ₹88 மட்டுமே கிடைத்திருக்கும். இதையே வோலாட்டிலிட்டி விவரிக்கிறது.",
            "analogy": "இரண்டு பேருந்துப் பயணங்கள், இரண்டும் ஒரு மணி நேரம். ஒன்று சீரான நெடுஞ்சாலையில், மற்றொன்று குண்டும் குழியுமான கிராமச் சாலையில்.\n\n"
                       "இருவரும் ஒரே நேரத்தில் சேர்கிறீர்கள், ஆனால் இரண்டாவது பயணத்தில் நீங்கள் மிக அதிகமாகக் குலுங்குகிறீர்கள்; பாதியில் இறங்க வேண்டியிருந்தால் நீங்கள் எங்கே இருப்பீர்கள் என்பதைக் கணிப்பது மிகக் கடினம்.\n\n"
                       "வோலாட்டிலிட்டி குலுக்கல்களை அளக்கிறது, சேருமிடத்தை அல்ல.",
        },
    },
    # ------------------------------------------------------------------
    "diversification-basics": {
        "resources": ["sebi_investor", "amfi", "ncfe"],
        "en": {
            "title": "What diversification does",
            "summary": "Spreading money across holdings reduces variability. It does not remove risk.",
            "simple": "Diversification means not putting all your money in one place.\n\n"
                      "If one thing does badly, the others may not, so the damage to the whole is smaller.\n\n"
                      "It lowers the impact of one bad outcome. It does not stop all losses, especially when everything falls together.",
            "detailed": "Diversification means spreading money across different holdings so that no single outcome decides the whole result.\n\n"
                        "The idea is that different assets do not all move together. Combining them tends to reduce the ups and downs of the total compared with holding just one.\n\n"
                        "What it does not do:\n"
                        "- It does not remove risk.\n"
                        "- It does not protect against broad market declines, when most things fall at once.\n"
                        "- It does not guarantee a positive result.\n\n"
                        "Holding many things that behave the same way is not much diversification. Diversification is a concept for understanding risk, not a recommendation about how anyone should divide their money.",
            "example": "Suppose ₹10,000 is invested in just one company, and that company's share price falls by half. The whole ₹10,000 becomes ₹5,000: a 50% loss.\n\n"
                       "Now suppose the same ₹10,000 is split equally across ten different companies, ₹1,000 each, and only one of them falls by half. That one becomes ₹500, so the total drops by ₹500: a 5% loss, if the others stay the same.\n\n"
                       "If all ten fall together, as can happen in a broad decline, spreading the money does not prevent the loss.",
            "analogy": "\"Don't put all your eggs in one basket.\" If you carry every egg in one basket and trip, you may lose them all. Spread across several baskets, one fall breaks only some.\n\n"
                       "But if the whole cart tips over, every basket falls at once. Diversification helps with a single slip, not with everything going wrong together.",
        },
        "hi": {
            "title": "विविधीकरण (डाइवर्सिफ़िकेशन) क्या करता है",
            "summary": "पैसा अलग-अलग जगह बाँटने से उतार-चढ़ाव कम होता है। जोखिम ख़त्म नहीं होता।",
            "simple": "डाइवर्सिफ़िकेशन का मतलब है अपना सारा पैसा एक ही जगह न लगाना।\n\n"
                      "अगर एक चीज़ ख़राब करे, तो ज़रूरी नहीं कि बाक़ी भी करें, इसलिए कुल नुकसान कम होता है।\n\n"
                      "यह एक बुरे नतीजे का असर घटाता है। यह सारे नुकसान नहीं रोकता, ख़ासकर जब सब कुछ एक साथ गिरे।",
            "detailed": "डाइवर्सिफ़िकेशन का मतलब है पैसा अलग-अलग निवेशों में बाँटना, ताकि कोई एक नतीजा पूरा परिणाम तय न करे।\n\n"
                        "विचार यह है कि अलग-अलग संपत्तियाँ एक साथ नहीं चलतीं। इन्हें मिलाने से कुल का उतार-चढ़ाव, सिर्फ़ एक रखने की तुलना में, आम तौर पर कम होता है।\n\n"
                        "यह क्या नहीं करता:\n"
                        "- जोखिम ख़त्म नहीं करता।\n"
                        "- पूरे बाज़ार की गिरावट से नहीं बचाता, जब ज़्यादातर चीज़ें एक साथ गिरती हैं।\n"
                        "- सकारात्मक नतीजे की गारंटी नहीं देता।\n\n"
                        "एक जैसा बर्ताव करने वाली कई चीज़ें रखना असल में ज़्यादा डाइवर्सिफ़िकेशन नहीं है। यह जोखिम समझने का एक विचार है, इस बात की सलाह नहीं कि किसी को पैसा कैसे बाँटना चाहिए।",
            "example": "मान लीजिए ₹10,000 सिर्फ़ एक कंपनी में लगे हैं और उसके शेयर का भाव आधा हो जाता है। पूरे ₹10,000 के ₹5,000 रह जाते हैं: 50% नुकसान।\n\n"
                       "अब मान लीजिए वही ₹10,000 दस अलग कंपनियों में बराबर, ₹1,000-₹1,000 लगे हैं, और सिर्फ़ एक का भाव आधा होता है। वह ₹500 का रह जाता है, कुल ₹500 घटता है: 5% नुकसान, अगर बाक़ी वैसे ही रहें।\n\n"
                       "अगर दसों एक साथ गिरें, जैसा पूरे बाज़ार की गिरावट में हो सकता है, तो पैसा बाँटने से नुकसान नहीं रुकता।",
            "analogy": "\"सारे अंडे एक टोकरी में मत रखो।\" अगर सारे अंडे एक टोकरी में हों और आप फिसल जाएँ, तो सब टूट सकते हैं। कई टोकरियों में बाँटें तो एक गिरने से कुछ ही टूटते हैं।\n\n"
                       "लेकिन अगर पूरी गाड़ी ही पलट जाए, तो सारी टोकरियाँ एक साथ गिरती हैं। डाइवर्सिफ़िकेशन एक फिसलन में मदद करता है, सब कुछ एक साथ बिगड़ने में नहीं।",
        },
        "ta": {
            "title": "பல்வகைப்படுத்தல் என்ன செய்கிறது",
            "summary": "பணத்தைப் பல இடங்களில் பிரிப்பது ஏற்ற இறக்கத்தைக் குறைக்கும். ஆபத்தை நீக்காது.",
            "simple": "பல்வகைப்படுத்தல் என்றால் உங்கள் பணம் முழுவதையும் ஒரே இடத்தில் போடாமல் இருப்பது.\n\n"
                      "ஒன்று மோசமாகப் போனாலும் மற்றவை அப்படிப் போகாமல் இருக்கலாம்; அதனால் மொத்த இழப்பு குறைவு.\n\n"
                      "ஒரு மோசமான விளைவின் தாக்கத்தை இது குறைக்கும். எல்லாம் ஒன்றாகச் சரியும்போது எல்லா இழப்புகளையும் தடுக்காது.",
            "detailed": "பல்வகைப்படுத்தல் என்றால் எந்த ஒரு விளைவும் முழு முடிவைத் தீர்மானிக்காதபடி பணத்தை வெவ்வேறு முதலீடுகளில் பிரிப்பது.\n\n"
                        "வெவ்வேறு சொத்துகள் எல்லாம் ஒன்றாக அசைவதில்லை என்பதே அடிப்படை. அவற்றைச் சேர்த்து வைப்பது, ஒன்றை மட்டும் வைத்திருப்பதை விட, மொத்தத்தின் ஏற்ற இறக்கத்தைப் பொதுவாகக் குறைக்கிறது.\n\n"
                        "இது என்ன செய்யாது:\n"
                        "- ஆபத்தை நீக்காது.\n"
                        "- பெரும்பாலானவை ஒன்றாகச் சரியும் பரந்த சந்தை வீழ்ச்சியிலிருந்து பாதுகாக்காது.\n"
                        "- நேர்மறை முடிவை உறுதி செய்யாது.\n\n"
                        "ஒரே மாதிரி நடந்துகொள்ளும் பலவற்றை வைத்திருப்பது உண்மையில் அதிக பல்வகைப்படுத்தல் அல்ல. இது ஆபத்தைப் புரிந்துகொள்ளும் ஒரு கருத்து; யாரும் பணத்தை எப்படிப் பிரிக்க வேண்டும் என்ற பரிந்துரை அல்ல.",
            "example": "₹10,000 ஒரே ஒரு நிறுவனத்தில் முதலீடு செய்யப்பட்டு, அந்த நிறுவனத்தின் பங்கு விலை பாதியாகக் குறைகிறது என்று வைத்துக்கொள்வோம். மொத்த ₹10,000 ₹5,000 ஆகிறது: 50% இழப்பு.\n\n"
                       "இப்போது அதே ₹10,000 பத்து வெவ்வேறு நிறுவனங்களில் சமமாக, தலா ₹1,000, பிரிக்கப்பட்டு, அவற்றில் ஒன்று மட்டும் பாதியாகக் குறைகிறது. அது ₹500 ஆகிறது, மொத்தம் ₹500 குறைகிறது: மற்றவை மாறாவிட்டால் 5% இழப்பு.\n\n"
                       "பரந்த வீழ்ச்சியில் நடப்பது போல பத்தும் ஒன்றாகச் சரிந்தால், பணத்தைப் பிரித்தது இழப்பைத் தடுக்காது.",
            "analogy": "\"எல்லா முட்டைகளையும் ஒரே கூடையில் வைக்காதே.\" எல்லா முட்டைகளும் ஒரே கூடையில் இருந்து நீங்கள் தடுக்கி விழுந்தால், எல்லாம் உடையலாம். பல கூடைகளில் பிரித்தால், ஒன்று விழுந்தால் சில மட்டுமே உடையும்.\n\n"
                       "ஆனால் முழு வண்டியே கவிழ்ந்தால், எல்லாக் கூடைகளும் ஒன்றாக விழும். பல்வகைப்படுத்தல் ஒரு தடுக்கலுக்கு உதவும்; எல்லாம் ஒன்றாகத் தவறும்போது அல்ல.",
        },
    },
    # ------------------------------------------------------------------
    "budgeting-first-steps": {
        "resources": ["ncfe", "rbi_kehta_hai"],
        "en": {
            "title": "First steps in budgeting",
            "summary": "Knowing what comes in, what goes out, and what you would do if income stopped for a month.",
            "simple": "A budget starts by simply noticing. For one month, write down all the money that comes in and all the money that goes out.\n\n"
                      "Then look: which costs are fixed every month, and which ones change?\n\n"
                      "Keeping some money aside for emergencies can stop a sudden expense from turning into a costly loan.",
            "detailed": "Budgeting starts with observation rather than restriction. For one month, write down what comes in and what goes out. Most people are surprised by at least one category.\n\n"
                        "Three questions that tend to matter more than any budgeting method:\n"
                        "1. What are my fixed commitments each month: rent, EMIs, school fees, bills?\n"
                        "2. What would I do if my income stopped for one month?\n"
                        "3. What am I currently paying interest on, and at what rate?\n\n"
                        "High-interest debt, such as unpaid credit card balances, often costs more than most investments can reasonably be expected to earn, which is why many people look at it first.\n\n"
                        "An emergency buffer kept somewhere you can reach quickly is what stops an unexpected expense from becoming a high-interest loan. How large it should be depends on your own situation.",
            "example": "Ravi earns ₹25,000 a month. After writing everything down for a month he sees:\n\n"
                       "Fixed: rent ₹8,000, phone and electricity ₹1,500, loan EMI ₹3,000.\n"
                       "Changing: groceries ₹6,000, travel ₹2,000, eating out and small purchases ₹3,500.\n\n"
                       "That leaves ₹1,000. He did not realise small purchases added up to ₹3,500. Nothing has to change immediately; he now knows where the money goes and can decide for himself what, if anything, to adjust.",
            "analogy": "A budget is like checking the water tank at home. Before deciding how to save water, you first look at which taps are running and how fast.\n\n"
                       "A small leak you never noticed can empty more than you think. An emergency buffer is the spare bucket you keep filled for the day the supply stops.",
        },
        "hi": {
            "title": "बजट बनाने के पहले कदम",
            "summary": "क्या आता है, क्या जाता है, और अगर एक महीने आमदनी रुक जाए तो आप क्या करेंगे।",
            "simple": "बजट की शुरुआत बस ध्यान देने से होती है। एक महीने तक जो भी पैसा आए और जो भी जाए, सब लिख लीजिए।\n\n"
                      "फिर देखिए: कौन से ख़र्च हर महीने तय हैं, और कौन से बदलते हैं?\n\n"
                      "आपात स्थिति के लिए कुछ पैसा अलग रखने से अचानक आया ख़र्च महँगे क़र्ज़ में नहीं बदलता।",
            "detailed": "बजट पाबंदी से नहीं, देखने से शुरू होता है। एक महीने तक जो आता है और जो जाता है, लिखिए। ज़्यादातर लोग किसी न किसी ख़र्च को देखकर हैरान होते हैं।\n\n"
                        "तीन सवाल जो किसी भी बजट तरीक़े से ज़्यादा मायने रखते हैं:\n"
                        "1. हर महीने मेरे तय ख़र्च क्या हैं: किराया, ईएमआई, स्कूल फ़ीस, बिल?\n"
                        "2. अगर एक महीने मेरी आमदनी रुक जाए तो मैं क्या करूँगा/करूँगी?\n"
                        "3. मैं अभी किन चीज़ों पर ब्याज दे रहा/रही हूँ, और किस दर पर?\n\n"
                        "ऊँचे ब्याज वाला क़र्ज़, जैसे क्रेडिट कार्ड का बकाया, अक्सर उससे ज़्यादा महँगा पड़ता है जितना ज़्यादातर निवेशों से उचित रूप से कमाने की उम्मीद की जा सकती है, इसीलिए कई लोग पहले उस पर ध्यान देते हैं।\n\n"
                        "जल्दी निकाले जा सकने वाली जगह रखा आपात फंड ही अचानक ख़र्च को ऊँचे ब्याज के क़र्ज़ में बदलने से रोकता है। यह कितना हो, यह आपकी अपनी स्थिति पर निर्भर करता है।",
            "example": "रवि महीने में ₹25,000 कमाता है। एक महीने सब लिखने के बाद वह देखता है:\n\n"
                       "तय: किराया ₹8,000, फ़ोन और बिजली ₹1,500, लोन की ईएमआई ₹3,000।\n"
                       "बदलने वाले: राशन ₹6,000, आना-जाना ₹2,000, बाहर खाना और छोटी ख़रीदारी ₹3,500।\n\n"
                       "बचते हैं ₹1,000। उसे पता नहीं था कि छोटी ख़रीदारी ₹3,500 तक पहुँच जाती है। तुरंत कुछ बदलना ज़रूरी नहीं; अब उसे पता है कि पैसा कहाँ जाता है और वह ख़ुद तय कर सकता है कि कुछ बदलना है या नहीं।",
            "analogy": "बजट घर की पानी की टंकी देखने जैसा है। पानी बचाने का तरीक़ा तय करने से पहले आप देखते हैं कि कौन से नल चल रहे हैं और कितनी तेज़।\n\n"
                       "एक छोटा रिसाव जिस पर ध्यान नहीं गया, सोच से ज़्यादा ख़ाली कर सकता है। आपात फंड वह भरी हुई बाल्टी है जो उस दिन के लिए रखी है जब सप्लाई रुक जाए।",
        },
        "ta": {
            "title": "பட்ஜெட் போடுவதன் முதல் படிகள்",
            "summary": "என்ன வருகிறது, என்ன போகிறது, ஒரு மாதம் வருமானம் நின்றால் என்ன செய்வீர்கள் என்பதை அறிவது.",
            "simple": "பட்ஜெட் வெறுமனே கவனிப்பதில் தொடங்குகிறது. ஒரு மாதத்துக்கு வரும் பணம், போகும் பணம் எல்லாவற்றையும் எழுதுங்கள்.\n\n"
                      "பிறகு பாருங்கள்: எந்தச் செலவுகள் ஒவ்வொரு மாதமும் நிலையானவை, எவை மாறுகின்றன?\n\n"
                      "அவசரத் தேவைக்காக கொஞ்சம் பணத்தைத் தனியாக வைப்பது, திடீர் செலவு அதிக வட்டிக் கடனாக மாறுவதைத் தடுக்கும்.",
            "detailed": "பட்ஜெட் கட்டுப்பாட்டில் அல்ல, கவனிப்பில் தொடங்குகிறது. ஒரு மாதத்துக்கு வருவதையும் போவதையும் எழுதுங்கள். பெரும்பாலானோர் குறைந்தது ஒரு செலவைப் பார்த்து வியப்படைகிறார்கள்.\n\n"
                        "எந்த பட்ஜெட் முறையை விடவும் முக்கியமான மூன்று கேள்விகள்:\n"
                        "1. ஒவ்வொரு மாதமும் என் நிலையான கடமைகள் என்ன: வாடகை, இஎம்ஐ, பள்ளிக் கட்டணம், கட்டணங்கள்?\n"
                        "2. ஒரு மாதம் என் வருமானம் நின்றால் நான் என்ன செய்வேன்?\n"
                        "3. இப்போது நான் எவற்றுக்கு வட்டி கட்டுகிறேன், எந்த விகிதத்தில்?\n\n"
                        "கிரெடிட் கார்டு நிலுவை போன்ற அதிக வட்டிக் கடன், பெரும்பாலான முதலீடுகளிலிருந்து நியாயமாக எதிர்பார்க்கக்கூடியதை விட அதிகம் செலவாகும்; அதனால்தான் பலர் அதை முதலில் கவனிக்கிறார்கள்.\n\n"
                        "விரைவாக எடுக்கக்கூடிய இடத்தில் வைக்கும் அவசர நிதிதான் எதிர்பாராத செலவு அதிக வட்டிக் கடனாக மாறுவதைத் தடுக்கிறது. அது எவ்வளவு இருக்க வேண்டும் என்பது உங்கள் சொந்தச் சூழலைப் பொறுத்தது.",
            "example": "ரவி மாதம் ₹25,000 சம்பாதிக்கிறார். ஒரு மாதம் எல்லாவற்றையும் எழுதிய பிறகு அவர் பார்க்கிறார்:\n\n"
                       "நிலையானவை: வாடகை ₹8,000, தொலைபேசி, மின்சாரம் ₹1,500, கடன் இஎம்ஐ ₹3,000.\n"
                       "மாறுபவை: மளிகை ₹6,000, பயணம் ₹2,000, வெளியே சாப்பிடுதல், சிறு வாங்குதல்கள் ₹3,500.\n\n"
                       "மீதம் ₹1,000. சிறு வாங்குதல்கள் ₹3,500 ஆகும் என்று அவருக்குத் தெரியவில்லை. உடனே எதையும் மாற்ற வேண்டியதில்லை; பணம் எங்கே போகிறது என்று இப்போது அவருக்குத் தெரியும், எதையாவது மாற்றுவதா என்று அவரே முடிவு செய்யலாம்.",
            "analogy": "பட்ஜெட் என்பது வீட்டுத் தண்ணீர்த் தொட்டியைச் சரிபார்ப்பது போன்றது. தண்ணீரைச் சேமிக்க முடிவு செய்வதற்கு முன், எந்தக் குழாய்கள் ஓடுகின்றன, எவ்வளவு வேகமாக என்று முதலில் பார்க்கிறீர்கள்.\n\n"
                       "கவனிக்காத ஒரு சிறு கசிவு நினைப்பதை விட அதிகம் காலி செய்யலாம். அவசர நிதி என்பது விநியோகம் நிற்கும் நாளுக்காக நிரப்பி வைத்த உதிரி வாளி.",
        },
    },
    # ------------------------------------------------------------------
    "recognising-pressure-tactics": {
        "resources": ["sebi_investor", "cybercrime", "sachet"],
        "en": {
            "title": "How to spot investment scams and pressure tactics",
            "summary": "The patterns used to stop you from checking: urgency, scarcity, authority and social proof.",
            "simple": "Most scams work by rushing you so you do not check.\n\n"
                      "Watch for: \"act today only\", \"only 3 seats left\", fake official names or logos, and screenshots of other people's profits.\n\n"
                      "The answer is always the same: slow down and verify on official websites. Nothing honest is lost by waiting a day.",
            "detailed": "Most financial fraud does not rely on a clever product. It relies on stopping you from checking.\n\n"
                        "Four patterns do most of the work:\n\n"
                        "Urgency: act now, today only, before it is too late. The purpose is to shorten the time you have to think.\n\n"
                        "Scarcity: limited seats, only three slots left. The purpose is to make hesitation feel like loss.\n\n"
                        "Authority: a regulator's name, an official-looking certificate, a uniform in a profile photo. The purpose is to borrow trust that has not been earned. Fake \"SEBI registration\" documents are common; check the number on sebi.gov.in yourself.\n\n"
                        "Social proof: screenshots of profits, a group full of enthusiastic members. The purpose is to make checking feel unnecessary. These groups are often filled with the scammers' own accounts.\n\n"
                        "The counter to all four is the same: slow down, and verify independently.",
            "example": "Lakshmi is added to a messaging group called \"Stock Tips VIP\". Members post profit screenshots every hour. An \"analyst\" with a SEBI logo in his photo says a special app will close registrations tonight, and asks her to deposit ₹20,000 to an individual's UPI ID.\n\n"
                       "Signals: urgency (tonight), authority (logo), social proof (screenshots), and payment to a personal account.\n\n"
                       "She leaves the group, searches SEBI's list of registered intermediaries for the name (it is not there), and reports the group on cybercrime.gov.in.",
            "analogy": "Think of a street magician. The trick works because your attention is pulled to the waving hand while the other hand does the work.\n\n"
                       "Urgency, excitement and other people cheering are the waving hand. Slowing down and looking at the other hand, who is actually receiving your money and whether they are registered, is how you see the trick.",
        },
        "hi": {
            "title": "निवेश धोखाधड़ी और दबाव की चालें कैसे पहचानें",
            "summary": "वे तरीक़े जो आपको जाँच करने से रोकते हैं: जल्दबाज़ी, कमी, अधिकार का दिखावा और दूसरों की मिसाल।",
            "simple": "ज़्यादातर धोखाधड़ी आपको जल्दबाज़ी में डालकर काम करती है ताकि आप जाँच न करें।\n\n"
                      "इन पर ध्यान दें: \"सिर्फ़ आज\", \"बस 3 सीटें बचीं\", नक़ली सरकारी नाम या लोगो, और दूसरों के मुनाफ़े के स्क्रीनशॉट।\n\n"
                      "जवाब हमेशा एक ही है: धीरे चलिए और आधिकारिक वेबसाइट पर जाँचिए। एक दिन रुकने से कुछ भी ईमानदार नहीं छूटता।",
            "detailed": "ज़्यादातर वित्तीय धोखाधड़ी किसी चतुर उत्पाद पर नहीं, बल्कि आपको जाँचने से रोकने पर टिकी होती है।\n\n"
                        "चार तरीक़े ज़्यादातर काम करते हैं:\n\n"
                        "जल्दबाज़ी: अभी करें, सिर्फ़ आज, देर हो जाएगी। मक़सद है आपके सोचने का समय घटाना।\n\n"
                        "कमी: सीमित सीटें, बस तीन जगह बचीं। मक़सद है हिचकिचाहट को नुकसान जैसा महसूस कराना।\n\n"
                        "अधिकार: नियामक का नाम, सरकारी जैसा दिखने वाला प्रमाणपत्र, प्रोफ़ाइल फ़ोटो में वर्दी। मक़सद है बिना कमाया भरोसा उधार लेना। नक़ली \"सेबी पंजीकरण\" दस्तावेज़ आम हैं; नंबर ख़ुद sebi.gov.in पर जाँचें।\n\n"
                        "दूसरों की मिसाल: मुनाफ़े के स्क्रीनशॉट, उत्साही सदस्यों से भरा ग्रुप। मक़सद है जाँच को बेकार महसूस कराना। ऐसे ग्रुप अक्सर धोखेबाज़ों के अपने ही खातों से भरे होते हैं।\n\n"
                        "चारों का जवाब एक है: धीरे चलिए, और ख़ुद स्वतंत्र रूप से जाँचिए।",
            "example": "लक्ष्मी को \"स्टॉक टिप्स वीआईपी\" नाम के एक मैसेजिंग ग्रुप में जोड़ा जाता है। सदस्य हर घंटे मुनाफ़े के स्क्रीनशॉट डालते हैं। फ़ोटो में सेबी लोगो वाला एक \"एनालिस्ट\" कहता है कि एक ख़ास ऐप में आज रात रजिस्ट्रेशन बंद हो जाएगा, और ₹20,000 एक व्यक्ति की यूपीआई आईडी पर जमा करने को कहता है।\n\n"
                       "संकेत: जल्दबाज़ी (आज रात), अधिकार (लोगो), दूसरों की मिसाल (स्क्रीनशॉट), और निजी खाते में भुगतान।\n\n"
                       "वह ग्रुप छोड़ देती है, सेबी की पंजीकृत मध्यस्थों की सूची में नाम खोजती है (नाम नहीं मिलता), और cybercrime.gov.in पर ग्रुप की शिकायत करती है।",
            "analogy": "सड़क के जादूगर को सोचिए। चाल इसलिए चलती है क्योंकि आपका ध्यान हिलते हुए हाथ पर खींच लिया जाता है, जबकि दूसरा हाथ असली काम करता है।\n\n"
                       "जल्दबाज़ी, उत्साह और दूसरों की तालियाँ वह हिलता हाथ हैं। धीरे होकर दूसरे हाथ को देखना, यानी असल में आपका पैसा कौन ले रहा है और क्या वह पंजीकृत है, यही चाल पकड़ने का तरीक़ा है।",
        },
        "ta": {
            "title": "முதலீட்டு மோசடிகளையும் அழுத்த உத்திகளையும் கண்டறிவது எப்படி",
            "summary": "நீங்கள் சரிபார்க்காமல் தடுக்கப் பயன்படும் முறைகள்: அவசரம், பற்றாக்குறை, அதிகாரம், பிறரின் சான்று.",
            "simple": "பெரும்பாலான மோசடிகள் உங்களை அவசரப்படுத்தி, நீங்கள் சரிபார்க்காமல் இருக்கச் செய்கின்றன.\n\n"
                      "இவற்றைக் கவனியுங்கள்: \"இன்று மட்டும்\", \"3 இடங்களே மீதம்\", போலி அதிகாரப்பூர்வ பெயர்கள் அல்லது சின்னங்கள், பிறரின் லாப ஸ்கிரீன்ஷாட்கள்.\n\n"
                      "பதில் எப்போதும் ஒன்றுதான்: நிதானமாக இருந்து அதிகாரப்பூர்வ இணையதளங்களில் சரிபாருங்கள். ஒரு நாள் காத்திருப்பதால் நேர்மையான எதுவும் இழக்கப்படாது.",
            "detailed": "பெரும்பாலான நிதி மோசடிகள் புத்திசாலித்தனமான தயாரிப்பை நம்பியிருப்பதில்லை. நீங்கள் சரிபார்ப்பதைத் தடுப்பதையே நம்பியிருக்கின்றன.\n\n"
                        "நான்கு முறைகள் பெரும்பாலான வேலையைச் செய்கின்றன:\n\n"
                        "அவசரம்: இப்போதே செய்யுங்கள், இன்று மட்டும், தாமதமாகிவிடும். நீங்கள் யோசிக்கும் நேரத்தைக் குறைப்பதே நோக்கம்.\n\n"
                        "பற்றாக்குறை: குறைந்த இடங்கள், மூன்று இடங்களே மீதம். தயக்கத்தை இழப்பாக உணர வைப்பதே நோக்கம்.\n\n"
                        "அதிகாரம்: ஒழுங்குமுறை அமைப்பின் பெயர், அதிகாரப்பூர்வமாகத் தோன்றும் சான்றிதழ், சுயவிவரப் படத்தில் சீருடை. சம்பாதிக்காத நம்பிக்கையைக் கடன் வாங்குவதே நோக்கம். போலி \"செபி பதிவு\" ஆவணங்கள் சகஜம்; எண்ணை நீங்களே sebi.gov.in-இல் சரிபாருங்கள்.\n\n"
                        "பிறரின் சான்று: லாப ஸ்கிரீன்ஷாட்கள், உற்சாகமான உறுப்பினர்கள் நிறைந்த குழு. சரிபார்ப்பு தேவையற்றதாக உணர வைப்பதே நோக்கம். இத்தகைய குழுக்கள் பெரும்பாலும் மோசடியாளர்களின் சொந்தக் கணக்குகளால் நிரம்பியவை.\n\n"
                        "நான்குக்கும் பதில் ஒன்றுதான்: நிதானியுங்கள், சுயமாகச் சரிபாருங்கள்.",
            "example": "லக்ஷ்மி \"ஸ்டாக் டிப்ஸ் விஐபி\" என்ற செய்திக் குழுவில் சேர்க்கப்படுகிறார். உறுப்பினர்கள் ஒவ்வொரு மணி நேரமும் லாப ஸ்கிரீன்ஷாட்களைப் பதிவிடுகிறார்கள். படத்தில் செபி சின்னம் உள்ள ஒரு \"ஆய்வாளர்\", ஒரு சிறப்புச் செயலியில் இன்றிரவு பதிவு முடியும் என்று சொல்லி, ஒரு தனிநபரின் யுபிஐ ஐடிக்கு ₹20,000 செலுத்தச் சொல்கிறார்.\n\n"
                       "அறிகுறிகள்: அவசரம் (இன்றிரவு), அதிகாரம் (சின்னம்), பிறரின் சான்று (ஸ்கிரீன்ஷாட்கள்), தனிநபர் கணக்குக்குப் பணம்.\n\n"
                       "அவர் குழுவிலிருந்து வெளியேறி, செபியின் பதிவு பெற்ற இடைத்தரகர் பட்டியலில் அந்தப் பெயரைத் தேடுகிறார் (அது இல்லை), cybercrime.gov.in-இல் குழுவைப் புகாரளிக்கிறார்.",
            "analogy": "தெரு மந்திரவாதியை நினைத்துப் பாருங்கள். அசையும் கையின் மீது உங்கள் கவனம் இழுக்கப்படுவதால்தான் தந்திரம் வேலை செய்கிறது; மற்றொரு கை உண்மையான வேலையைச் செய்கிறது.\n\n"
                       "அவசரம், உற்சாகம், பிறரின் கைதட்டல் ஆகியவை அந்த அசையும் கை. நிதானித்து மற்றொரு கையைப் பார்ப்பது, அதாவது உங்கள் பணத்தை உண்மையில் யார் பெறுகிறார், அவர் பதிவு பெற்றவரா என்று பார்ப்பதே தந்திரத்தைக் கண்டுபிடிக்கும் வழி.",
        },
    },
    # ------------------------------------------------------------------
    "basics-risk-and-return": {
        "resources": ["ncfe", "sebi_investor"],
        "en": {
            "title": "Risk and return, honestly",
            "summary": "Why higher potential return always comes with higher uncertainty, and what that means in practice.",
            "simple": "If something might give you more money, it can also lose more money. Higher possible gain comes with more uncertainty.\n\n"
                      "Safer options usually pay less. Riskier ones might pay more, or might lose.\n\n"
                      "If someone offers high returns with no risk, that combination does not exist. Treat it as a warning.",
            "detailed": "Across investments, a higher potential return comes with higher uncertainty about the outcome. This is not a rule someone imposed; it follows from the fact that people have to be compensated for accepting a less predictable result.\n\n"
                        "\"Risk\" here means the range of possible outcomes, including losing part of the money, getting it back later than planned, or not being able to sell when you need to.\n\n"
                        "The practical consequence: if something offers a return well above what safe, regulated options pay, it is carrying more risk somewhere, even if the person offering it does not say so.\n\n"
                        "An offer of high return with low or no risk describes something that does not exist. That combination is itself the warning signal.\n\n"
                        "Understanding this does not tell you what to invest in. It tells you which claims to be sceptical about.",
            "example": "Option 1: a bank fixed deposit pays a fixed, modest interest that is written in the deposit receipt.\n"
                       "Option 2: shares of a company might rise a lot, stay flat, or fall a lot; nobody knows in advance.\n"
                       "Option 3: a stranger offers \"18% a year, fixed, completely safe\".\n\n"
                       "Options 1 and 2 are honest about their trade-off: low uncertainty with lower return, or higher uncertainty with possibly higher return. Option 3 claims the high return of Option 2 with the safety of Option 1. That is exactly the claim to verify before anything else.",
            "analogy": "Think of travel choices. The government bus is slow but predictable. A private taxi is faster but can cost more if traffic is bad. A shortcut through the fields might be quickest, or you might get stuck in the mud.\n\n"
                       "Someone selling a route that is \"fastest, cheapest and guaranteed never to get stuck\" is describing a road that no one has ever found.",
        },
        "hi": {
            "title": "जोखिम और रिटर्न, सच्चाई से",
            "summary": "ज़्यादा संभावित रिटर्न के साथ हमेशा ज़्यादा अनिश्चितता क्यों आती है, और व्यवहार में इसका क्या मतलब है।",
            "simple": "जिससे ज़्यादा पैसा मिल सकता है, उसमें ज़्यादा पैसा डूब भी सकता है। ज़्यादा संभावित फ़ायदे के साथ ज़्यादा अनिश्चितता आती है।\n\n"
                      "सुरक्षित विकल्प आम तौर पर कम देते हैं। जोखिम वाले ज़्यादा दे सकते हैं, या नुकसान भी कर सकते हैं।\n\n"
                      "अगर कोई बिना जोखिम के ऊँचा रिटर्न दे, तो ऐसा मेल होता ही नहीं। इसे चेतावनी समझिए।",
            "detailed": "निवेश में ज़्यादा संभावित रिटर्न के साथ नतीजे को लेकर ज़्यादा अनिश्चितता आती है। यह किसी का बनाया नियम नहीं; यह इस बात से निकलता है कि कम अनुमान लगाने योग्य नतीजा स्वीकार करने के बदले लोगों को कुछ ज़्यादा मिलना चाहिए।\n\n"
                        "यहाँ \"जोखिम\" का मतलब है संभावित नतीजों का दायरा, जिसमें पैसे का कुछ हिस्सा खोना, योजना से देर से वापस मिलना, या ज़रूरत पर बेच न पाना शामिल है।\n\n"
                        "व्यावहारिक नतीजा: अगर कोई चीज़ सुरक्षित, विनियमित विकल्पों से काफ़ी ज़्यादा रिटर्न दे रही है, तो उसमें कहीं न कहीं ज़्यादा जोखिम है, चाहे पेश करने वाला यह न बताए।\n\n"
                        "ऊँचे रिटर्न के साथ कम या शून्य जोखिम का प्रस्ताव ऐसी चीज़ बताता है जो होती ही नहीं। यही मेल अपने आप में चेतावनी है।\n\n"
                        "यह समझ यह नहीं बताती कि किसमें निवेश करें। यह बताती है कि किन दावों पर शक करना चाहिए।",
            "example": "विकल्प 1: बैंक फ़िक्स्ड डिपॉज़िट एक तय, मामूली ब्याज देता है जो जमा रसीद पर लिखा होता है।\n"
                       "विकल्प 2: किसी कंपनी के शेयर बहुत बढ़ सकते हैं, वहीं रह सकते हैं, या बहुत गिर सकते हैं; पहले से कोई नहीं जानता।\n"
                       "विकल्प 3: एक अजनबी \"साल का 18%, फ़िक्स्ड, पूरी तरह सुरक्षित\" देने की बात करता है।\n\n"
                       "विकल्प 1 और 2 अपने सौदे के बारे में ईमानदार हैं: कम अनिश्चितता के साथ कम रिटर्न, या ज़्यादा अनिश्चितता के साथ शायद ज़्यादा रिटर्न। विकल्प 3 विकल्प 2 का ऊँचा रिटर्न और विकल्प 1 की सुरक्षा, दोनों का दावा करता है। ठीक इसी दावे की सबसे पहले जाँच होनी चाहिए।",
            "analogy": "यात्रा के विकल्प सोचिए। सरकारी बस धीमी है पर भरोसेमंद। प्राइवेट टैक्सी तेज़ है पर जाम हो तो महँगी पड़ सकती है। खेतों से होकर शॉर्टकट सबसे जल्दी हो सकता है, या आप कीचड़ में फँस सकते हैं।\n\n"
                       "जो \"सबसे तेज़, सबसे सस्ता और कभी न फँसने की गारंटी\" वाला रास्ता बेच रहा है, वह ऐसी सड़क बता रहा है जो आज तक किसी को नहीं मिली।",
        },
        "ta": {
            "title": "ஆபத்தும் வருமானமும், நேர்மையாக",
            "summary": "அதிக சாத்தியமான வருமானம் ஏன் எப்போதும் அதிக நிச்சயமின்மையுடன் வருகிறது, நடைமுறையில் அதன் அர்த்தம் என்ன.",
            "simple": "அதிகப் பணம் தரக்கூடிய ஒன்று அதிகப் பணத்தை இழக்கவும் செய்யலாம். அதிக சாத்தியமான லாபத்துடன் அதிக நிச்சயமின்மை வருகிறது.\n\n"
                      "பாதுகாப்பான வழிகள் பொதுவாகக் குறைவாகத் தரும். ஆபத்தானவை அதிகம் தரலாம், அல்லது இழக்கலாம்.\n\n"
                      "ஆபத்தே இல்லாமல் அதிக வருமானம் என்று யாராவது சொன்னால், அப்படி ஒரு சேர்க்கை இல்லை. அதை எச்சரிக்கையாகக் கருதுங்கள்.",
            "detailed": "முதலீடுகளில், அதிக சாத்தியமான வருமானம் விளைவைப் பற்றிய அதிக நிச்சயமின்மையுடன் வருகிறது. இது யாரோ விதித்த விதி அல்ல; குறைவாகக் கணிக்கக்கூடிய முடிவை ஏற்பதற்கு மக்களுக்கு ஈடு தரப்பட வேண்டும் என்பதிலிருந்து இது வருகிறது.\n\n"
                        "இங்கே \"ஆபத்து\" என்றால் சாத்தியமான விளைவுகளின் வரம்பு: பணத்தின் ஒரு பகுதியை இழப்பது, திட்டமிட்டதை விடத் தாமதமாகத் திரும்பப் பெறுவது, தேவைப்படும்போது விற்க முடியாமல் போவது உட்பட.\n\n"
                        "நடைமுறை விளைவு: பாதுகாப்பான, ஒழுங்குபடுத்தப்பட்ட வழிகளை விட மிக அதிக வருமானம் தருவதாக ஒன்று சொன்னால், அது எங்கோ அதிக ஆபத்தைச் சுமக்கிறது, வழங்குபவர் அதைச் சொல்லாவிட்டாலும்.\n\n"
                        "அதிக வருமானமும் குறைந்த அல்லது பூஜ்ய ஆபத்தும் என்ற வாய்ப்பு இல்லாத ஒன்றை விவரிக்கிறது. அந்தச் சேர்க்கையே எச்சரிக்கை அறிகுறி.\n\n"
                        "இதைப் புரிந்துகொள்வது எதில் முதலீடு செய்வது என்று சொல்லாது. எந்தக் கூற்றுகளைச் சந்தேகிக்க வேண்டும் என்று சொல்கிறது.",
            "example": "வழி 1: வங்கி நிலை வைப்பு, வைப்பு ரசீதில் எழுதப்பட்ட நிலையான, மிதமான வட்டி தருகிறது.\n"
                       "வழி 2: ஒரு நிறுவனத்தின் பங்குகள் நிறைய ஏறலாம், அப்படியே இருக்கலாம், அல்லது நிறைய இறங்கலாம்; முன்கூட்டியே யாருக்கும் தெரியாது.\n"
                       "வழி 3: ஒரு அந்நியர் \"வருடத்துக்கு 18%, நிலையானது, முழுப் பாதுகாப்பு\" என்று சொல்கிறார்.\n\n"
                       "வழி 1, 2 தங்கள் பரிமாற்றம் பற்றி நேர்மையானவை: குறைந்த நிச்சயமின்மையுடன் குறைந்த வருமானம், அல்லது அதிக நிச்சயமின்மையுடன் ஒருவேளை அதிக வருமானம். வழி 3, வழி 2-இன் அதிக வருமானத்தையும் வழி 1-இன் பாதுகாப்பையும் ஒருசேரக் கூறுகிறது. இந்தக் கூற்றைத்தான் முதலில் சரிபார்க்க வேண்டும்.",
            "analogy": "பயண வழிகளை நினைத்துப் பாருங்கள். அரசுப் பேருந்து மெதுவானது ஆனால் கணிக்கக்கூடியது. தனியார் டாக்ஸி வேகமானது, ஆனால் நெரிசல் இருந்தால் அதிகம் செலவாகும். வயல்கள் வழியான குறுக்குவழி மிக வேகமாக இருக்கலாம், அல்லது சேற்றில் மாட்டிக்கொள்ளலாம்.\n\n"
                       "\"மிக வேகம், மிக மலிவு, ஒருபோதும் மாட்டாது என்று உத்தரவாதம்\" என்று ஒரு வழியை விற்பவர், இதுவரை யாரும் கண்டுபிடிக்காத சாலையை விவரிக்கிறார்.",
        },
    },
}

# Filter chips on /learn -> the LearningContent categories each one covers.
FILTER_GROUPS: dict[str, tuple[str, ...]] = {
    "basics": ("basics", "market-concepts"),
    "mutual-funds": ("mutual-funds",),
    "scams": ("scams",),
    "rights": ("investor-rights",),
    "upi": ("digital-safety",),
    "volatility": ("risk-volatility",),
    "budget": ("budgeting",),
}


def filter_group(category: str) -> str:
    for key, categories in FILTER_GROUPS.items():
        if category in categories:
            return key
    return "basics"


def lesson_text(slug: str, language: str) -> dict | None:
    """All four modes plus title/summary for ``slug`` in ``language``.

    Falls back to English only if a language is missing, which the tests
    guard against for every published lesson.
    """
    lesson = LESSONS.get(slug)
    if lesson is None:
        return None
    return lesson.get(language) or lesson["en"]


def resources_for(slug: str, language: str) -> list[dict]:
    lesson = LESSONS.get(slug) or {}
    out = []
    for key in lesson.get("resources", []):
        res = RESOURCES[key]
        url = res["url"]
        domain = url.split("//", 1)[-1].split("/", 1)[0]
        out.append(
            {
                "name": res["name"],
                "url": url,
                "domain": domain,
                "about": res["about"].get(language) or res["about"]["en"],
            }
        )
    return out
