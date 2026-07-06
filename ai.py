"""
CaptionAI Finder - AI Beyni (Groq, Llama 3.3 70B)
=================================================

Ucretsiz + yuksek limit (gunde ~14.400 istek), OpenAI-uyumlu REST (SDK yok).
Key: https://console.groq.com/keys . Coklu key: biri bitince sonrakine gecer.

Hiper-ozel, TEK DILDE, temiz ve insan gibi DM/email uretir.
"""

import json
import random
import re
from typing import List, Optional

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"

# Latin disi istenmeyen alfabeler (dil karisimini yakalamak icin)
CJK_RE = re.compile(r"[\u3000-\u9fff\u3040-\u30ff\uac00-\ud7af]")  # Cince/Japonca/Korece
ARABIC_RE = re.compile(r"[\u0600-\u06ff]")


class QuotaError(Exception):
    """Tum key'ler tukendi/kota bitti."""


_STYLE_SEEDS = [
    "bio'sundan somut bir detayla ac",
    "icerigi hakkinda samimi, spesifik bir iltifatla ac",
    "nisindeki bir zorluga deginerek ac",
    "kisa merakli bir soruyla ac",
    "sohbete devam eder gibi rahat ac",
]

LANG_NAMES = {"tr": "Turkish", "en": "English", "es": "Spanish", "de": "German", "fr": "French", "ar": "Arabic"}

LANG_RULES = {
    "tr": "Yalnizca akici, dogru, dogal TURKCE yaz. Native bir Turk gibi. Bozuk ifade YASAK: 'videolarini takiliyorum' (YANLIS), dogrusu 'videolarini takip ediyorum' ya da 'izliyorum'.",
    "en": "Write ONLY in fluent, natural English.",
    "es": "Write ONLY in fluent, natural Spanish.",
    "de": "Write ONLY in fluent, natural German.",
    "fr": "Write ONLY in fluent, natural French.",
    "ar": "Write ONLY in fluent, natural Arabic.",
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
        """Dil karisimi/bozuk cikti kontrolu. Kotu ise False -> fallback kullanilir."""
        if not text or len(text) < 15:
            return False
        if CJK_RE.search(text):
            return False  # Cince/Japonca/Korece sizmis -> reddet
        if lang != "ar" and ARABIC_RE.search(text):
            return False  # Arapca istenmediyse Arap harfi -> reddet
        return True

    def generate_dm(self, creator, lang, product_pitch, learned_tips="", link_url="", channel="dm") -> str:
        name = creator.get("nickname") or creator.get("username", "")
        bio = creator.get("bio", "")
        followers = creator.get("followers", 0)
        seed = random.choice(_STYLE_SEEDS)
        lang_name = LANG_NAMES.get(lang, "English")

        if channel == "email":
            link_rule = f"- Bu bir EMAIL. Linki bir kez, dogal sekilde ekle: {link_url}. 3-5 samimi, insan gibi cumle."
        else:
            link_rule = "- Bu bir TikTok DM. ASLA link/URL koyma (TikTok engelliyor). 'link biomda' de. En fazla 3 kisa cumle."

        system = (
            "Sen 16 yasinda bir kurucusun ve TikTok icerik ureticilerine birebir, samimi mesaj yaziyorsun. "
            "Yazdigin mesaj gercek bir insanin elle yazdigi gibi olmali: sicak, spesifik, kisa, asla sablon/AI gibi degil."
        )
        user = f"""Tek bir kisa mesaj yaz. DIL: {lang_name} - {LANG_RULES.get(lang, LANG_RULES['en'])}

COK ONEMLI KURALLAR:
- SADECE {lang_name} dilinde yaz. Baska hicbir dil, hicbir yabanci alfabe (Cince, Japonca, Arapca vb.) KULLANMA.
- Ciktida sadece mesaj metni olsun. Aciklama, secenek, birden fazla versiyon YOK. TEK mesaj.
- Dilbilgisi kusursuz ve dogal olmali.

KISI (ona ozel yaz):
- ad: {name}
- bio: {bio or '(bos)'}
- takipci: {followers}

URUN (dogal deginin, satis yapma): {product_pitch}

STIL: {seed}. Ona ozgu somut bir seye deginmeye calis. Bir gercek fayda + samimi bir geri bildirim ricasi. En fazla 1 emoji, basa koyma.
YASAK: 'unlock', 'game-changer', kurumsal ton, 'sana ulasmak istedim', 'merhaba diyeyim dedim', abartili ovgu.
{link_rule}
{('- Daha cok cevap alan yaklasim: ' + learned_tips) if learned_tips else ''}

SADECE mesaj metnini yaz."""
        out = self._chat(system, user, temperature=0.7, max_tokens=320)
        out = _tidy(out)
        if not self._is_clean(out, lang):
            raise RuntimeError("AI cikti dil kontrolunden gecemedi")  # app.py fallback'e duser
        return out

    def analyze_fit(self, creator) -> dict:
        name = creator.get("nickname") or creator.get("username", "")
        bio = creator.get("bio", "")
        followers = creator.get("followers", 0)
        user = ("Assess if this TikTok creator is a good target for a caption-writing tool. Weak/short captions = better fit. "
                f"CREATOR: name={name}; followers={followers}; bio=\"{bio or '(empty)'}\". "
                'Return STRICT JSON only: {"fit_score":0-100,"reason":"one short sentence","angle":"one short sentence"}')
        return _safe_json(self._chat("Return only strict JSON.", user, 0.3, 150), {"fit_score": 50, "reason": "", "angle": ""})

    def analyze_reply(self, dm_sent, reply_text, lang="tr") -> dict:
        user = (f"Creator replied. MY DM: {dm_sent}\nREPLY: {reply_text}\n"
                'Return STRICT JSON only: {"sentiment":"pos"|"neu"|"neg","category":"interested"|"question"|"not_interested"|"spammy","suggested_reply":"short human reply in their language"}')
        return _safe_json(self._chat("Return only strict JSON.", user, 0.5, 200), {"sentiment": "neu", "category": "question", "suggested_reply": ""})

    def learn_from_stats(self, samples) -> str:
        if not samples:
            return ""
        compact = [{"m": (s.get("message", "")[:140]), "replied": bool(s.get("replied"))} for s in samples[:30]]
        user = ("DMs and replies (JSON): " + json.dumps(compact, ensure_ascii=False)
                + ". 2-3 one-line tips (no markdown) on what gets MORE replies. Output only tips.")
        try:
            return self._chat("Concise growth analyst.", user, 0.5, 180)
        except QuotaError:
            raise
        except Exception:
            return ""


def _tidy(text: str) -> str:
    """Fazla bosluk/satir, tirnak sarmasi temizligi."""
    t = (text or "").strip()
    # Bazen model mesaji tirnak icine alir
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
    a, b = s.find("{"), s.rfind("}")
    if a != -1 and b != -1 and b > a:
        s = s[a:b + 1]
    try:
        d = json.loads(s)
        if isinstance(d, dict):
            return {**default, **d}
    except Exception:
        pass
    return default
