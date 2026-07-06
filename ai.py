"""
CaptionAI Finder - AI Beyni
===========================

İki backend:
  - apikey : generativelanguage REST API (SDK GEREKMEZ, her zaman calisir)
             https://aistudio.google.com/apikey
  - vertex : google-genai SDK (opsiyonel) - kota bitince project+location ile

Kota/anahtar bitince QuotaError firlatir; app.py yakalar.
"""

import json
import random
from typing import List, Optional

import requests

GL_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Vertex icin opsiyonel SDK
try:
    from google import genai as _vertex_genai
    from google.genai import types as _vertex_types
except Exception:
    _vertex_genai = None
    _vertex_types = None


class QuotaError(Exception):
    """Kota/anahtar bitti -> yeni anahtar ya da Vertex'e gec."""


# Her cagriya cesitlilik katan stil tohumlari (ayni sablon tekrarini kirar).
_STYLE_SEEDS = [
    "open with a specific detail from their bio",
    "open with a genuine compliment about one concrete thing in their content",
    "open by relating to a struggle creators in their niche have",
    "open with a short curious question",
    "open casually like continuing a conversation",
]


class AIBrain:
    def __init__(self, backend="apikey", api_key="", project="", location="", model=""):
        self.backend = backend
        if backend == "vertex":
            if _vertex_genai is None:
                raise RuntimeError("Vertex icin google-genai kurulu degil (pip install google-genai).")
            if not project or not location:
                raise RuntimeError("Vertex icin project ve location gerekli.")
            self.model = model or "gemini-2.5-flash"
            self.client = _vertex_genai.Client(vertexai=True, project=project, location=location)
        else:
            if not api_key or "YAPISTIR" in api_key:
                raise RuntimeError("Gecerli bir Gemini API key yok.")
            self.api_key = api_key.strip()
            self.model = model or "gemini-2.5-flash"
            self.client = None

    # --- Dusuk seviye uretim ---
    def _gen(self, prompt: str, temperature: float = 1.0, image=None) -> str:
        if self.backend == "vertex":
            return self._gen_vertex(prompt, temperature, image)
        return self._gen_rest(prompt, temperature, image)

    def _gen_rest(self, prompt, temperature, image) -> str:
        parts = [{"text": prompt}]
        if image is not None:
            b64, mime = image
            parts.append({"inline_data": {"mime_type": mime, "data": b64}})
        url = f"{GL_BASE}/{self.model}:generateContent"
        body = {"contents": [{"parts": parts}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": 700}}
        try:
            r = requests.post(url, params={"key": self.api_key}, json=body, timeout=60)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"AI baglanti hatasi: {e}")
        if r.status_code == 429:
            raise QuotaError(r.text[:200])
        if r.status_code >= 400:
            low = r.text.lower()
            if "quota" in low or "resource_exhausted" in low or "exhausted" in low:
                raise QuotaError(r.text[:200])
            raise RuntimeError(f"AI hatasi ({r.status_code}): {r.text[:200]}")
        try:
            data = r.json()
            return (data["candidates"][0]["content"]["parts"][0]["text"] or "").strip()
        except Exception:
            return ""

    def _gen_vertex(self, prompt, temperature, image) -> str:
        try:
            contents = [prompt]
            if image is not None:
                import base64
                b64, mime = image
                contents.append(_vertex_types.Part.from_bytes(data=base64.b64decode(b64), mime_type=mime))
            cfg = _vertex_types.GenerateContentConfig(temperature=temperature, max_output_tokens=700)
            resp = self.client.models.generate_content(model=self.model, contents=contents, config=cfg)
            return (getattr(resp, "text", "") or "").strip()
        except Exception as e:  # noqa: BLE001
            low = str(e).lower()
            if any(k in low for k in ["quota", "429", "resource_exhausted", "exhausted"]):
                raise QuotaError(str(e))
            raise RuntimeError(f"Vertex hatasi: {e}")

    # --- Baglanti testi (panel 'AI: ok' icin) ---
    def ping(self) -> bool:
        txt = self._gen("Reply with just: OK", temperature=0)
        return "ok" in (txt or "").lower()

    # --- 10/10, farkli farki, dogru dilde DM ---
    def generate_dm(self, creator, lang, product_pitch, learned_tips="", link_url="", channel="dm") -> str:
        lang_rules = {
            "tr": "Write in fluent, natural, correct Turkish. Native Gen-Z Turkish, not translated. "
                  "BANNED broken phrases: 'videolarini takiliyorum', 'takiliyorum'. Correct is 'videolarini takip ediyorum' / 'izliyorum'.",
            "en": "Write in fluent, natural English.",
            "es": "Write in fluent, natural Spanish.",
            "de": "Write in fluent, natural German.",
            "fr": "Write in fluent, natural French.",
            "ar": "Write in fluent, natural Arabic.",
        }
        lang_names = {"tr": "Turkish", "en": "English", "es": "Spanish", "de": "German", "fr": "French", "ar": "Arabic"}
        name = creator.get("nickname") or creator.get("username", "")
        bio = creator.get("bio", "")
        followers = creator.get("followers", 0)
        seed = random.choice(_STYLE_SEEDS)

        if channel == "email":
            link_rule = f"- This is an EMAIL. Include the link once, naturally: {link_url}. 4-6 warm human sentences."
        else:
            link_rule = ("- This is a TikTok DM. NEVER include any link/URL. Say the link is in my bio. Max 3 short sentences.")

        prompt = f"""You are a real 16-year-old founder writing a 1:1 outreach message to a TikTok creator.
Goal: sound 100% human and warm, and make each message clearly DIFFERENT from others. If it reads like AI or a template, you failed.

CREATOR: name={name}; followers={followers}; bio=\"{bio or '(empty)'}\"

LANGUAGE: {lang_names.get(lang,'English')}. {lang_rules.get(lang, lang_rules['en'])}
Grammar and word choice MUST be flawless and natural for a native speaker. No awkward or broken phrases.

WHAT I MADE (mention naturally, never hard-sell): {product_pitch}

STYLE FOR THIS ONE (follow it, this makes each message unique): {seed}.
- Warm, casual, real. One genuine reason it could help THEM, then a soft ask for honest feedback.
- At most ONE emoji, never start with it. Vary sentence rhythm.
- BANNED vibes/words: unlock, elevate, game-changer, boost, corporate tone, 'I came across', 'I wanted to reach out', 'hope this finds you'.
{link_rule}
{('- Lessons from what got replies: ' + learned_tips) if learned_tips else ''}

Output ONLY the message text."""
        return self._gen(prompt, temperature=1.1)

    def analyze_fit(self, creator) -> dict:
        name = creator.get("nickname") or creator.get("username", "")
        bio = creator.get("bio", "")
        followers = creator.get("followers", 0)
        prompt = (
            "Assess if this TikTok creator is a good target for a caption-writing tool. "
            "Weak/short/generic captions = better fit. "
            f"CREATOR: name={name}; followers={followers}; bio=\"{bio or '(empty)'}\". "
            'Return STRICT JSON only: {"fit_score":0-100,"reason":"one short sentence","angle":"one short sentence"}'
        )
        return _safe_json(self._gen(prompt, temperature=0.4), {"fit_score": 50, "reason": "", "angle": ""})

    def analyze_profile(self, image_bytes, mime="image/png") -> dict:
        import base64
        b64 = base64.b64encode(image_bytes).decode()
        prompt = ('Look at this TikTok profile screenshot. Return STRICT JSON only: '
                  '{"niche":str,"tone":str,"captions_weak":true/false,"fit_score":0-100,"approach":one short sentence}')
        return _safe_json(self._gen(prompt, temperature=0.4, image=(b64, mime)),
                          {"niche": "", "tone": "", "captions_weak": False, "fit_score": 50, "approach": ""})

    def analyze_reply(self, dm_sent, reply_text, lang="tr") -> dict:
        prompt = (f"Creator replied to my DM. MY DM: {dm_sent}\nTHEIR REPLY: {reply_text}\n"
                  'Return STRICT JSON only: {"sentiment":"pos"|"neu"|"neg","category":"interested"|"question"|"not_interested"|"spammy","suggested_reply":"short human reply in their language"}')
        return _safe_json(self._gen(prompt, temperature=0.6), {"sentiment": "neu", "category": "question", "suggested_reply": ""})

    def learn_from_stats(self, samples) -> str:
        if not samples:
            return ""
        compact = [{"m": (s.get("message", "")[:180]), "replied": bool(s.get("replied"))} for s in samples[:50]]
        prompt = ("Past DMs and whether they got replies (JSON): " + json.dumps(compact, ensure_ascii=False)
                  + ". In 2-3 one-line tips (no markdown), what wording/length/angle gets MORE replies? Output only tips.")
        try:
            return self._gen(prompt, temperature=0.5)
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
