"""
CaptionAI Finder - AI Beyni (google-genai: API key VEYA Vertex AI)
=================================================================

İki backend:
  1) API key   -> aistudio.google.com/apikey (hızlı başlangıç, ücretsiz kota)
  2) Vertex AI -> project + location + model (kota bitince buraya geç)
     Örn: project=captionai-501010, location=europe-central2,
          model=gemini-3.1-flash-lite-preview

Vertex kimlik doğrulaması API key ile DEĞİL, Google Cloud kimlik bilgisiyle olur:
  - `gcloud auth application-default login`  (en kolay), YA DA
  - GOOGLE_APPLICATION_CREDENTIALS = service-account.json yolu
Proje + bölge verilirse SDK bu kimlik bilgilerini otomatik kullanır.

Yaptığı işler:
  generate_dm     -> 10/10, sahici, ASLA AI/soğuk durmayan DM (DM'de link YOK)
  analyze_fit     -> profil GÖRSELİ olmadan, metinden uygunluk skoru + yaklaşım
  analyze_profile -> (opsiyonel) ekran görüntüsü ile gören analiz
  analyze_reply   -> gelen yanıtı sınıflandır + cevap öner
  learn_from_stats-> geçmiş yanıtlardan öğren

Kota/anahtar bitince QuotaError fırlatır; app.py yakalayıp yeni anahtar/backend ister.
"""

import json
import os
from typing import List, Optional

try:
    from google import genai
    from google.genai import types as gtypes
except ImportError:
    genai = None
    gtypes = None


class QuotaError(Exception):
    """Kota/anahtar bitti -> yeni anahtar ya da Vertex'e geç."""


class AIBrain:
    """
    backend='apikey' -> api_key gerekir.
    backend='vertex' -> project + location gerekir (model opsiyonel).
    """
    def __init__(
        self,
        backend: str = "apikey",
        api_key: str = "",
        project: str = "",
        location: str = "",
        model: str = "",
    ):
        if genai is None:
            raise RuntimeError("google-genai kurulu degil. pip install -r requirements.txt")
        self.backend = backend
        if backend == "vertex":
            if not project or not location:
                raise RuntimeError("Vertex icin project ve location gerekli.")
            self.model = model or "gemini-3.1-flash-lite-preview"
            self.client = genai.Client(vertexai=True, project=project, location=location)
        else:
            if not api_key or "YAPISTIR" in api_key:
                raise RuntimeError("Gecerli bir Gemini API key yok.")
            self.model = model or "gemini-2.5-flash"
            self.client = genai.Client(api_key=api_key)

    # --- Ortak çağrı ---
    def _gen(self, contents) -> str:
        try:
            resp = self.client.models.generate_content(model=self.model, contents=contents)
            return (getattr(resp, "text", "") or "").strip()
        except Exception as e:  # noqa: BLE001
            msg = str(e).lower()
            if any(k in msg for k in ["quota", "429", "resource_exhausted", "rate limit", "exhausted"]):
                raise QuotaError(str(e))
            raise

    # --- 1) 10/10, sahici DM. DM'de link YOK. ---
    def generate_dm(
        self, creator: dict, lang: str, product_pitch: str,
        learned_tips: str = "", link_url: str = "", channel: str = "dm",
    ) -> str:
        """channel='dm' -> linksiz (bio'ya yönlendir). channel='email' -> link_url gövdeye girer."""
        lang_names = {"tr": "Turkish", "en": "English", "es": "Spanish",
                      "de": "German", "fr": "French", "ar": "Arabic"}
        lang_name = lang_names.get(lang, "English")
        name = creator.get("nickname") or creator.get("username", "")
        bio = creator.get("bio", "")
        followers = creator.get("followers", 0)

        if channel == "email":
            link_rule = (
                f"- This is an EMAIL. Include the link exactly once, naturally: {link_url}\n"
                "- Slightly longer is ok (4-6 sentences), still warm and human, not corporate."
            )
        else:
            link_rule = (
                "- This is a TikTok DM. NEVER put any link or URL (TikTok blocks link DMs). "
                "Instead say the link is in my bio.\n"
                "- Max 3 short sentences."
            )

        prompt = f"""You are a real 16-year-old founder writing to a TikTok creator. Write ONE message in {lang_name}.
This must read as 10/10 human. If it smells even slightly like AI or a cold mass-DM, you failed.

CREATOR:
- name: {name}
- bio: {bio or '(empty)'}
- followers: {followers}

WHAT I MADE (weave in naturally, never hard-sell):
{product_pitch}

VOICE (obey all):
- Sound like a real teen texting, not a brand. Lowercase where natural, casual, warm, a little raw.
- Open with something specific and true about THEM (from bio/niche). No generic "love your content".
- One genuine reason it could help them, then a soft ask for honest feedback. Never salesy.
- At most ONE emoji, and never start with it. Vary rhythm, use a short fragment.
- BANNED words/vibes: unlock, elevate, game-changer, boost, "as a fellow", "I came across", "I wanted to reach out", "hope this finds you", perfect symmetry, corporate tone.
{link_rule}
{('- Apply what got replies before: ' + learned_tips) if learned_tips else ''}

Output ONLY the message text."""
        return self._gen(prompt)

    # --- 2) Metin bazlı uygunluk (GÖRSEL GEREKMEZ) ---
    def analyze_fit(self, creator: dict) -> dict:
        """bio/niş/takipçiden uygunluk. Döner: {fit_score, reason, angle}."""
        name = creator.get("nickname") or creator.get("username", "")
        bio = creator.get("bio", "")
        followers = creator.get("followers", 0)
        lang = creator.get("lang", "en")
        prompt = f"""Assess if this TikTok creator is a good target for a caption-writing tool.
Weak/short/generic captions or no clear caption effort = BETTER fit (higher score).

CREATOR: name={name}; followers={followers}; language={lang}; bio=\"{bio or '(empty)'}\"

Return STRICT JSON only:
{{"fit_score": 0-100, "reason": "one short sentence why", "angle": "one short sentence on how to pitch them"}}"""
        return _safe_json(self._gen(prompt), default={"fit_score": 50, "reason": "", "angle": ""})

    # --- 3) (Opsiyonel) Gören analiz: ekran görüntüsü ---
    def analyze_profile(self, image_bytes: bytes, mime: str = "image/png") -> dict:
        img = gtypes.Part.from_bytes(data=image_bytes, mime_type=mime)
        prompt = (
            "Look at this TikTok profile screenshot as a growth expert. Return STRICT JSON only: "
            '{"niche": str, "tone": str, "captions_weak": true/false, "fit_score": 0-100, '
            '"approach": one short sentence}'
        )
        raw = self._gen([prompt, img])
        return _safe_json(raw, default={"niche": "", "tone": "", "captions_weak": False,
                                        "fit_score": 50, "approach": ""})

    # --- 4) Yanıt analizi ---
    def analyze_reply(self, dm_sent: str, reply_text: str, lang: str = "tr") -> dict:
        prompt = f"""A creator replied to my outreach. Classify and draft a natural reply.
MY DM: {dm_sent}
THEIR REPLY: {reply_text}
Return STRICT JSON only:
{{"sentiment":"pos"|"neu"|"neg","category":"interested"|"question"|"not_interested"|"spammy","suggested_reply":"short human reply in their language"}}"""
        return _safe_json(self._gen(prompt), default={"sentiment": "neu", "category": "question", "suggested_reply": ""})

    # --- 5) Öğrenme ---
    def learn_from_stats(self, samples: List[dict]) -> str:
        if not samples:
            return ""
        compact = [{"m": (s.get("message", "")[:200]), "replied": bool(s.get("replied")),
                    "sent": s.get("sentiment", "")} for s in samples[:60]]
        prompt = (
            "Past outreach DMs and whether they got a reply (JSON): "
            + json.dumps(compact, ensure_ascii=False)
            + ". In 2-3 one-line tips (no markdown), tell me what wording/length/angle gets MORE replies. Output only tips."
        )
        try:
            return self._gen(prompt)
        except QuotaError:
            raise
        except Exception:
            return ""


def _safe_json(raw: str, default: dict) -> dict:
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
        data = json.loads(s)
        if isinstance(data, dict):
            return {**default, **data}
    except Exception:
        pass
    return default
