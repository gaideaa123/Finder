"""
CaptionAI Finder - AI Beyni (Groq, Llama 3.3 70B)
=================================================

Neden Groq? Ucretsiz + yuksek limit (gunde ~14.400 istek), kredi karti yok,
OpenAI-uyumlu REST (SDK GEREKMEZ -> kurulum hatasi olmaz), LPU ile cok hizli.
Key: https://console.groq.com/keys

Hiper-ozellestirme: her creator'in bio/nis/dil/takipci verisinden, o kisiye
ozel, insan gibi mesaj uretir. Coklu key: biri bitince (429) sonrakine gecer.
"""

import json
import random
from typing import List, Optional

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


class QuotaError(Exception):
    """Tum key'ler tukendi/kota bitti."""


_STYLE_SEEDS = [
    "open with a specific detail from their bio",
    "open with a genuine, concrete compliment about their content",
    "open by relating to a real struggle creators in their niche have",
    "open with a short curious question about their niche",
    "open casually, like continuing a conversation",
    "open by referencing their follower size / momentum naturally",
]

LANG_RULES = {
    "tr": "Akici, dogal, DOGRU Turkce yaz (native Gen-Z). Bozuk ifade YASAK (or. 'videolarini takiliyorum' YANLIS; dogrusu 'videolarini takip ediyorum' / 'izliyorum').",
    "en": "Write in fluent, natural English.",
    "es": "Write in fluent, natural Spanish.",
    "de": "Write in fluent, natural German.",
    "fr": "Write in fluent, natural French.",
    "ar": "Write in fluent, natural Arabic.",
}
LANG_NAMES = {"tr": "Turkish", "en": "English", "es": "Spanish", "de": "German", "fr": "French", "ar": "Arabic"}


class AIBrain:
    def __init__(self, api_keys, model: str = DEFAULT_MODEL):
        if isinstance(api_keys, str):
            api_keys = [api_keys]
        self.api_keys = [k.strip() for k in api_keys if k and k.strip()]
        if not self.api_keys:
            raise RuntimeError("Gecerli bir Groq API key yok.")
        self.model = model or DEFAULT_MODEL
        self._i = 0

    def _chat(self, system: str, user: str, temperature: float = 1.0, max_tokens: int = 400) -> str:
        last_err = ""
        # Mevcut key'den basla, biterse sirayla digerlerini dene.
        for _ in range(len(self.api_keys)):
            key = self.api_keys[self._i]
            try:
                r = requests.post(
                    GROQ_URL,
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": [{"role": "system", "content": system},
                                     {"role": "user", "content": user}],
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                    timeout=45,
                )
            except Exception as e:  # noqa: BLE001
                last_err = str(e)
                self._i = (self._i + 1) % len(self.api_keys)
                continue
            if r.status_code == 429:
                last_err = "429 rate/quota"
                self._i = (self._i + 1) % len(self.api_keys)
                continue
            if r.status_code >= 400:
                last_err = f"{r.status_code}: {r.text[:150]}"
                # Anahtar gecersizse sonrakine gec
                if r.status_code in (401, 403):
                    self._i = (self._i + 1) % len(self.api_keys)
                    continue
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

    # --- Hiper-ozellestirilmis DM/email ---
    def generate_dm(self, creator, lang, product_pitch, learned_tips="", link_url="", channel="dm") -> str:
        name = creator.get("nickname") or creator.get("username", "")
        bio = creator.get("bio", "")
        followers = creator.get("followers", 0)
        seed = random.choice(_STYLE_SEEDS)
        lang_name = LANG_NAMES.get(lang, "English")

        if channel == "email":
            link_rule = f"- This is an EMAIL. Include the link once, naturally: {link_url}. 4-6 warm human sentences. Add a short subject-worthy first line."
        else:
            link_rule = "- This is a TikTok DM. NEVER include any link/URL (TikTok blocks them). Say the link is in my bio. Max 3 short sentences."

        system = (
            "You are a real 16-year-old founder doing 1:1 creator outreach. You write messages that are "
            "indistinguishable from a genuine human DM: warm, specific, casual, never templated, never salesy. "
            "If a message reads like AI or a mass-blast, you have failed."
        )
        user = f"""Write ONE outreach message in {lang_name}. {LANG_RULES.get(lang, LANG_RULES['en'])}
Grammar must be flawless and natural for a native speaker.

CREATOR (personalize hard, use real details):
- name: {name}
- bio: {bio or '(empty)'}
- followers: {followers}

WHAT I MADE (mention naturally, do not hard-sell): {product_pitch}

MAKE IT HYPER-PERSONAL & UNIQUE:
- {seed}.
- Reference something concrete about THEM (from bio/niche). If bio is empty, infer from niche and be specific.
- One genuine reason it could help THEM specifically, then a soft ask for honest feedback.
- At most ONE emoji, never start with it. Vary rhythm, use a short fragment.
- BANNED: unlock, elevate, game-changer, boost, corporate tone, 'I came across', 'I wanted to reach out', 'hope this finds you', generic 'love your content'.
{link_rule}
{('- Lessons from what got replies before: ' + learned_tips) if learned_tips else ''}

Output ONLY the message text, nothing else."""
        return self._chat(system, user, temperature=1.05, max_tokens=350)

    def analyze_fit(self, creator) -> dict:
        name = creator.get("nickname") or creator.get("username", "")
        bio = creator.get("bio", "")
        followers = creator.get("followers", 0)
        user = ("Assess if this TikTok creator is a good target for a caption-writing tool. "
                "Weak/short/generic captions = better fit. "
                f"CREATOR: name={name}; followers={followers}; bio=\"{bio or '(empty)'}\". "
                'Return STRICT JSON only: {"fit_score":0-100,"reason":"one short sentence","angle":"one short sentence"}')
        return _safe_json(self._chat("You return only strict JSON.", user, temperature=0.3, max_tokens=150),
                          {"fit_score": 50, "reason": "", "angle": ""})

    def analyze_reply(self, dm_sent, reply_text, lang="tr") -> dict:
        user = (f"Creator replied to my DM. MY DM: {dm_sent}\nTHEIR REPLY: {reply_text}\n"
                'Return STRICT JSON only: {"sentiment":"pos"|"neu"|"neg","category":"interested"|"question"|"not_interested"|"spammy","suggested_reply":"short human reply in their language"}')
        return _safe_json(self._chat("You return only strict JSON.", user, temperature=0.5, max_tokens=200),
                          {"sentiment": "neu", "category": "question", "suggested_reply": ""})

    def learn_from_stats(self, samples) -> str:
        if not samples:
            return ""
        compact = [{"m": (s.get("message", "")[:160]), "replied": bool(s.get("replied"))} for s in samples[:40]]
        user = ("Past DMs and whether they got replies (JSON): " + json.dumps(compact, ensure_ascii=False)
                + ". In 2-3 one-line tips (no markdown), what wording/length/angle gets MORE replies? Output only tips.")
        try:
            return self._chat("You are a concise growth analyst.", user, temperature=0.5, max_tokens=200)
        except QuotaError:
            raise
        except Exception:
            return ""


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
