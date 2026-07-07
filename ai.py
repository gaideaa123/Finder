"""
CaptionAI Finder - AI Beyni (Groq, Llama 3.3 70B)
=================================================

Ucretsiz + yuksek limit, OpenAI-uyumlu REST (SDK yok).
Key: https://console.groq.com/keys . Coklu key: biri bitince sonrakine gecer.

- Hiper-ozel, TEK DILDE, temiz, INSAN gibi email uretir (16 yasinda kurucu hikayesi).
- Uretilen metni ikinci bir gecisle DUZELTIR (yazim/dilbilgisi hatasi birakmaz).
- Nis/dil/ulkeye gore HASHTAG uretir.
"""

import json
import random
import re
from typing import List, Optional

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"

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
    "tr": "Yalnizca akici, dogru, dogal TURKCE yaz. Native bir Turk gibi. Dilbilgisi ve yazim KUSURSUZ olmali. Bozuk ifade YASAK: 'videolarini takiliyorum' (YANLIS), dogrusu 'videolarini takip ediyorum' ya da 'izliyorum'.",
    "en": "Write ONLY in fluent, natural, grammatically flawless English.",
    "es": "Write ONLY in fluent, natural, grammatically flawless Spanish.",
    "de": "Write ONLY in fluent, natural, grammatically flawless German.",
    "fr": "Write ONLY in fluent, natural, grammatically flawless French.",
    "ar": "Write ONLY in fluent, natural, grammatically flawless Arabic.",
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
            return False
        if lang != "ar" and ARABIC_RE.search(text):
            return False
        return True

    def _proofread(self, text: str, lang: str) -> str:
        """Ikinci gecis: SADECE yazim/dilbilgisi hatalarini duzeltir, tonu/anlami korur.
        Boylece gonderilen mailde kelime hatasi kalmaz."""
        lang_name = LANG_NAMES.get(lang, "English")
        system = ("You are a meticulous native " + lang_name + " proofreader. Fix ONLY spelling, "
                  "grammar and word-choice errors. Keep the exact same meaning, tone, casual style, "
                  "length and any emoji. Do NOT add greetings, explanations or quotes. Return ONLY the corrected text.")
        try:
            out = self._chat(system, text, temperature=0.1, max_tokens=320)
            out = _tidy(out)
            return out if self._is_clean(out, lang) else text
        except QuotaError:
            raise
        except Exception:
            return text

    def generate_dm(self, creator, lang, product_pitch, learned_tips="", link_url="", channel="email") -> str:
        name = creator.get("nickname") or creator.get("username", "")
        bio = creator.get("bio", "")
        followers = creator.get("followers", 0)
        seed = random.choice(_STYLE_SEEDS)
        lang_name = LANG_NAMES.get(lang, "English")

        if channel == "email":
            link_rule = f"- Bu bir EMAIL. Linki bir kez, dogal sekilde ekle: {link_url}."
            length_rule = "- 4-6 samimi, insan gibi cumle. Kisa bir kisisel HIKAYE anlat."
        else:
            link_rule = "- Bu bir TikTok DM. ASLA link/URL koyma. 'link biomda' de. En fazla 3 kisa cumle."
            length_rule = "- En fazla 3 kisa cumle."

        system = (
            "Sen 16 yasinda, tek basina kod yazan bir lise ogrencisi ve kurucususun. "
            "Icerik ureticilerine birebir, sicak ve samimi mesajlar yaziyorsun. "
            "Yazdigin mesaj gercek bir insanin elle yazdigi gibi olmali: dogal, spesifik, "
            "asla sablon/AI gibi degil. Dilbilgisi ve yazim KUSURSUZ."
        )
        user = f"""Tek bir mesaj yaz. DIL: {lang_name} - {LANG_RULES.get(lang, LANG_RULES['en'])}

COK ONEMLI KURALLAR:
- SADECE {lang_name} dilinde yaz. Baska hicbir dil/alfabe (Cince, Japonca, Arapca vb.) KULLANMA.
- Ciktida sadece mesaj metni olsun. Aciklama, secenek, birden fazla versiyon YOK. TEK mesaj.
- Yazim ve dilbilgisi KUSURSUZ, dogal olmali. Tek bir kelime hatasi bile olmasin.

KIM OLDUGUN (mesaja dogal serpistir, abartma):
- 16 yasinda, tek basina bu araci gelistiren birisin. Kisa, gercekci, samimi bir hikaye anlat:
  neden yaptigin (caption yazmak seni/arkadaslarini zorluyordu gibi), tek basina yaptigin.
- Bombastik degil, mutevazi ve icten. "16 yasindayim" bilgisini dogal biçimde gecir.

KISI (ona ozel yaz):
- ad: {name}
- bio: {bio or '(bos)'}
- takipci: {followers}

URUN (dogal deginin, satis yapma): {product_pitch}

STIL: {seed}. Ona ozgu somut bir seye degin. Bir gercek fayda + samimi bir geri bildirim ricasi. En fazla 1 emoji, basa koyma.
{length_rule}
YASAK: 'unlock', 'game-changer', kurumsal ton, 'sana ulasmak istedim', 'merhaba diyeyim dedim', abartili ovgu.
{link_rule}
{('- Daha cok cevap alan yaklasim: ' + learned_tips) if learned_tips else ''}

SADECE mesaj metnini yaz."""
        out = self._chat(system, user, temperature=0.7, max_tokens=380)
        out = _tidy(out)
        if not self._is_clean(out, lang):
            raise RuntimeError("AI cikti dil kontrolunden gecemedi")  # app.py fallback'e duser
        # Email icin ikinci gecis: yazim/dilbilgisi hatalarini temizle
        if channel == "email":
            out = self._proofread(out, lang)
        return out

    def generate_hashtags(self, lang="tr", countries=None, niche_hint="", count=12) -> List[str]:
        """Nis/dil/ulkeye gore, caption araci icin IDEAL hedef hashtag'ler uretir.
        (Cok icerik ureten ama caption'i zayif olabilecek yaraticilar.)"""
        lang_name = LANG_NAMES.get(lang, "English")
        loc = ", ".join(countries) if countries else lang_name
        system = ("You are a TikTok growth expert. You output ONLY a JSON array of hashtag strings, "
                  "no '#', lowercase, no spaces, no explanation.")
        user = (
            f"Give {count} TikTok hashtags in {lang_name} (market: {loc}) to find CONTENT CREATORS "
            f"who post a lot but likely struggle with writing captions (ideal customers for an AI caption tool). "
            f"Prefer niches like food, daily vlog, fashion/GRWM, skincare, fitness, travel, books, small business/sellers. "
            + (f"Focus hint: {niche_hint}. " if niche_hint else "")
            + 'Return ONLY a JSON array, e.g. ["yemektarifi","gunlukvlog"].'
        )
        try:
            raw = self._chat(system, user, temperature=0.6, max_tokens=250)
        except QuotaError:
            raise
        except Exception:
            return []
        arr = _safe_json(raw, [])
        if not isinstance(arr, list):
            # bazen virgullu metin donebilir
            arr = [t.strip() for t in re.split(r"[,\n]", raw) if t.strip()]
        out, seen = [], set()
        for h in arr:
            h = str(h).strip().lstrip("#").replace(" ", "").lower()
            if h and h not in seen:
                seen.add(h)
                out.append(h)
        return out[:count]

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
    # dizi mi obje mi
    for op, cl in (("[", "]"), ("{", "}")):
        a, b = s.find(op), s.rfind(cl)
        if a != -1 and b != -1 and b > a:
            try:
                return json.loads(s[a:b + 1])
            except Exception:
                continue
    return default
