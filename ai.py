"""
CaptionAI Finder - AI Beyni (Groq, Llama 3.3 70B)
=================================================

- Hiper-ozel, TEK DILDE, temiz, INSAN gibi email uretir (16 yasinda kurucu hikayesi).
- SERT DIL KILIDI: kisi Turkce ise TURKCE, Ingilizce ise INGILIZCE. Karisik/bozuk
  cikti REDDEDILIR -> temiz fallback kullanilir (asla bozuk mesaj gonderilmez).
- Kisiye ozel email KONUSU (subject) uretir.
"""

import json
import random
import re
from typing import List, Optional

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"

CJK_RE = re.compile(r"[\u3000-\u9fff\u3040-\u30ff\uac00-\ud7af]")
ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
LATIN_RE = re.compile(r"[a-zA-Z]")

BAD_PHRASES = [
    "baglantiim kuruldu", "ba\u011flant\u0131\u0131m kuruldu", "seninle baglanti",
    "olarak seninle", "connected with you as", "i connected with",
    "reaching out to you", "sana ulasmak istedim", "merhaba diyeyim",
    "as someone who", "i wanted to reach",
]

EN_STOPWORDS = {"the", "and", "your", "you", "with", "for", "this", "that", "content",
                "videos", "really", "love", "built", "tool", "would", "feedback", "reaching"}
TR_STOPWORDS = {"ve", "bir", "icin", "i\u00e7in", "videolarini", "senin", "cok", "\u00e7ok",
                "yaptim", "yapt\u0131m", "merhaba", "selam", "arac", "ara\u00e7", "gelistirdim"}

class QuotaError(Exception):
    """Tum key'ler tukendi/kota bitti."""

_STYLE_SEEDS = [
    "bio'sundan somut bir detayla ac",
    "icerigi hakkinda samimi, spesifik bir iltifatla ac",
    "nisindeki bir zorluga deginerek ac",
    "kisa merakli bir soruyla ac",
]

LANG_NAMES = {"tr": "Turkish", "en": "English", "es": "Spanish", "de": "German", "fr": "French", "ar": "Arabic"}

LANG_RULES = {
    "tr": "SADECE akici, dogal, KUSURSUZ Turkce yaz. Native bir Turk gibi. Tek bir Ingilizce kelime bile kullanma. 'baglantiim kuruldu', 'seninle baglanti kurdum' gibi bozuk/cevrilmis ifadeler YASAK.",
    "en": "Write ONLY in fluent, natural, flawless English. Not a single Turkish or foreign word.",
    "es": "Write ONLY in fluent, natural, flawless Spanish.",
    "de": "Write ONLY in fluent, natural, flawless German.",
    "fr": "Write ONLY in fluent, natural, flawless French.",
    "ar": "Write ONLY in fluent, natural, flawless Arabic.",
}

class AIBrain:
    def __init__(self, api_keys, model: str = DEFAULT_MODEL):
        if isinstance(api_keys, str):
            api_keys = [api_keys]
        self.api_keys = [k.strip() for k in api_keys if k and k.strip()]
        if not self.api_keys:
            raise RuntimeError("Gecerli bir Groq API key yok.")
        self.model = model or DEFAULT_MODEL
        self._i = 0

    def _chat(self, system: str, user: str, temperature: float = 0.7, max_tokens: int = 350) -> str:
        last_err = ""
        for _ in range(len(self.api_keys)):
            key = self.api_keys[self._i]
            try:
                r = requests.post(
                    GROQ_URL,
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": self.model,
                          "messages": [{"role": "system", "content": system},
                                       {"role": "user", "content": user}],
                          "temperature": temperature, "max_tokens": max_tokens},
                    timeout=45,
                )
            except Exception as e:  # noqa: BLE001
                last_err = str(e); self._i = (self._i + 1) % len(self.api_keys); continue
            if r.status_code == 429:
                last_err = "429"; self._i = (self._i + 1) % len(self.api_keys); continue
            if r.status_code >= 400:
                last_err = f"{r.status_code}: {r.text[:150]}"
                if r.status_code in (401, 403):
                    self._i = (self._i + 1) % len(self.api_keys); continue
                raise RuntimeError(f"AI hatasi ({last_err})")
            try:
                return (r.json()["choices"][0]["message"]["content"] or "").strip()
            except Exception:
                return ""
        raise QuotaError(last_err or "Tum Groq key'leri tukendi")

    def ping(self) -> bool:
        try:
            return "ok" in self._chat("You are a test.", "Reply with just: OK", temperature=0, max_tokens=5).lower()
        except QuotaError:
            raise
        except Exception:
            return False

    def _is_clean(self, text: str, lang: str) -> bool:
        """Bozuk/karisik dil kontrolu. Kotu ise False -> temiz fallback kullanilir."""
        if not text or len(text) < 15:
            return False
        low = text.lower()
        if CJK_RE.search(text):
            return False
        if lang != "ar" and ARABIC_RE.search(text):
            return False
        if lang == "ar" and len(LATIN_RE.findall(text)) > 8:
            return False
        for bad in BAD_PHRASES:
            if bad in low:
                return False
        words = set(re.findall(r"[a-z\u00e7\u011f\u0131\u00f6\u015f\u00fc]+", low))
        if lang == "tr" and len(words & EN_STOPWORDS) >= 3:
            return False
        if lang == "en":
            if len(words & TR_STOPWORDS) >= 2:
                return False
            if len(re.findall(r"[\u011f\u0131\u015f]", low)) > 2:
                return False
        return True

    def generate_dm(self, creator, lang, product_pitch, learned_tips="", link_url="", channel="email") -> str:
        name = creator.get("nickname") or creator.get("username", "")
        bio = creator.get("bio", "")
        followers = creator.get("followers", 0)
        seed = random.choice(_STYLE_SEEDS)
        lang_name = LANG_NAMES.get(lang, "English")

        if channel == "email":
            link_rule = f"- Bu bir EMAIL. Linki bir kez, dogal sekilde ekle: {link_url}."
            length_rule = "- 4-6 kisa, samimi, insan gibi cumle. Kisa bir kisisel hikaye anlat."
        else:
            link_rule = "- Bu bir TikTok DM. ASLA link koyma. 'link biomda' de. En fazla 3 kisa cumle."
            length_rule = "- En fazla 3 kisa cumle."

        system = (
            f"You write ONLY in {lang_name}. You are a 16-year-old solo founder writing a warm, "
            f"personal outreach message to a TikTok creator. It must read like a real human hand-wrote it: "
            f"natural, specific, never template-like, flawless grammar. {LANG_RULES.get(lang, LANG_RULES['en'])}"
        )
        user = f"""Write ONE short message, entirely in {lang_name}.

HARD RULES:
- Output ONLY in {lang_name}. Even if the creator's bio below is in another language, YOU still write in {lang_name}.
- Output ONLY the message text. No explanations, no options, no subject line, no quotes. ONE message.
- Perfect, natural grammar. Zero awkward or translated-sounding phrases.
- Do NOT copy random words from the bio (like brand/food names) into your sentences.

WHO YOU ARE (weave in naturally, humble, short story): a 16-year-old who built this tool alone because writing captions was hard for you and your friends. Mention being 16 naturally.

PERSON (write specifically for them):
- name: {name}
- bio: {bio or '(empty)'}
- followers: {followers}

PRODUCT (mention naturally, don't hard-sell): {product_pitch}

STYLE: {seed}. One real benefit + a warm ask for honest feedback. At most 1 emoji, not at the start.
FORBIDDEN: 'unlock', 'game-changer', corporate tone, 'I wanted to reach out', overblown praise, any phrase like 'connected with you as ...'.
{link_rule}
{length_rule}
{('- Approach that gets more replies: ' + learned_tips) if learned_tips else ''}

Write ONLY the message text in {lang_name}."""
        out = _tidy(self._chat(system, user, temperature=0.6, max_tokens=380))
        if not self._is_clean(out, lang):
            out = _tidy(self._chat(system, user + f"\n\nONEMLI: Kesinlikle SADECE {lang_name}. Onceki denemede dil karisti.",
                                   temperature=0.3, max_tokens=380))
            if not self._is_clean(out, lang):
                raise RuntimeError("AI cikti dil kontrolunden gecemedi")
        return out

    def generate_subject(self, creator, lang="tr") -> str:
        """Kisiye ozel, kisa, spam gibi olmayan email KONUSU."""
        name = creator.get("nickname") or creator.get("username", "")
        bio = creator.get("bio", "")
        lang_name = LANG_NAMES.get(lang, "English")
        system = f"You write ONLY in {lang_name}. Output a single short email subject, no quotes, no emoji."
        user = (f"Write a short, personal, non-spammy email SUBJECT in {lang_name} (3-6 words) for reaching out to "
                f"TikTok creator '{name}' (bio: {bio or 'n/a'}). Casual, human, references them or their content. "
                f"Output ONLY the subject line.")
        try:
            s = self._chat(system, user, temperature=0.7, max_tokens=30)
            s = _tidy(s.splitlines()[0]) if s else ""
            if s and self._is_clean(s + " ok ok ok", lang):
                return s[:80]
        except QuotaError:
            raise
        except Exception:
            pass
        return _fallback_subject(creator, lang)

    def generate_hashtags(self, lang="tr", countries=None, niche_hint="", count=12) -> List[str]:
        lang_name = LANG_NAMES.get(lang, "English")
        loc = ", ".join(countries) if countries else lang_name
        system = ("You are a TikTok growth expert. Output ONLY a JSON array of hashtag strings, "
                  "no '#', lowercase, no spaces, no explanation.")
        user = (f"Give {count} TikTok hashtags in {lang_name} (market: {loc}) to find CONTENT CREATORS "
                f"who post a lot but likely struggle writing captions (ideal customers for an AI caption tool). "
                f"Prefer food, daily vlog, fashion/GRWM, skincare, fitness, travel, books, small business/sellers. "
                + (f"Focus: {niche_hint}. " if niche_hint else "")
                + 'Return ONLY a JSON array like ["yemektarifi","gunlukvlog"].')
        try:
            raw = self._chat(system, user, temperature=0.6, max_tokens=250)
        except QuotaError:
            raise
        except Exception:
            return []
        arr = _safe_json(raw, [])
        if not isinstance(arr, list):
            arr = [t.strip() for t in re.split(r"[,\n]", raw) if t.strip()]
        out, seen = [], set()
        for h in arr:
            h = str(h).strip().lstrip("#").replace(" ", "").lower()
            if h and h not in seen:
                seen.add(h); out.append(h)
        return out[:count]

    def analyze_reply(self, dm_sent, reply_text, lang="tr") -> dict:
        user = (f"Creator replied. MY EMAIL: {dm_sent}\nREPLY: {reply_text}\n"
                'Return STRICT JSON only: {"sentiment":"pos"|"neu"|"neg","category":"interested"|"question"|"not_interested"|"spammy","suggested_reply":"short human reply in their language"}')
        return _safe_json(self._chat("Return only strict JSON.", user, 0.5, 200), {"sentiment": "neu", "category": "question", "suggested_reply": ""})

    def learn_from_stats(self, samples) -> str:
        if not samples:
            return ""
        compact = [{"m": (s.get("message", "")[:140]), "replied": bool(s.get("replied"))} for s in samples[:30]]
        user = ("Emails and replies (JSON): " + json.dumps(compact, ensure_ascii=False)
                + ". 2-3 one-line tips (no markdown) on what gets MORE replies. Output only tips.")
        try:
            return self._chat("Concise growth analyst.", user, 0.5, 180)
        except QuotaError:
            raise
        except Exception:
            return ""

def _fallback_subject(creator, lang="tr") -> str:
    name = creator.get("nickname") or creator.get("username", "")
    subs = {
        "tr": f"{name}, icerigin cok iyi",
        "en": f"{name}, love your content",
        "es": f"{name}, me encanta tu contenido",
        "de": f"{name}, dein content ist top",
        "fr": f"{name}, j'adore ton contenu",
        "ar": f"{name}",
    }
    return (subs.get(lang, subs["en"]).strip().strip(",").strip()) or "hey"

def _tidy(text: str) -> str:
    t = (text or "").strip()
    if len(t) >= 2 and t[0] in "\"'" and t[-1] in "\"'":
        t = t[1:-1].strip()
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def _safe_json(raw, default):
    if not raw:
        return default
    s = raw.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
    for op, cl in (("[", "]"), ("{", "}")):
        a, b = s.find(op), s.rfind(cl)
        if a != -1 and b != -1 and b > a:
            try:
                return json.loads(s[a:b + 1])
            except Exception:
                continue
    return default
