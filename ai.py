"""
CaptionAI Finder - AI Beyni (Google Gemini)
===========================================

Model: gemini-2.5-flash (ücretsiz katman, multimodal = metin + görüntü/vision).
Araştırma: 2026 itibarıyla ücretsiz + güçlü + 'gören' en iyi seçenek; free tier
Flash modelleriyle sınırlı, Pro paralı. 2.5 Flash ~10 RPM / ~250K TPM / ~500 RPD.

Bu modül dört iş yapar:
  1) generate_dm      -> creator'a özel, gerçekten insansı DM üretir
  2) analyze_profile  -> profil EKRAN GÖRÜNTÜSÜNÜ gören AI ile analiz eder
  3) analyze_reply    -> gelen yanıtı sınıflandırır + duygu/aksiyon önerir
  4) learn_from_stats -> geçmiş yanıtlardan öğrenip DM stratejisi çıkarır

Kota/anahtar bitince (429 / quota) QuotaError fırlatır; app.py bunu yakalayıp
kullanıcıdan yeni anahtar ister ve kaldığı yerden devam eder.
"""

import json
import os
from typing import List, Optional

try:
    import google.generativeai as genai
except ImportError:
    genai = None

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


class QuotaError(Exception):
    """Gemini kotası/anahtarı bitti -> yeni anahtar gerek."""


class AIBrain:
    def __init__(self, api_key: str, model_name: str = MODEL_NAME):
        if genai is None:
            raise RuntimeError("google-generativeai kurulu degil. pip install -r requirements.txt")
        if not api_key or "YAPISTIR" in api_key:
            raise RuntimeError("Gecerli bir Gemini API key yok.")
        self.api_key = api_key
        self.model_name = model_name
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    # --- Ortak çağrı (kota hatasını yakalar) ---
    def _generate(self, parts) -> str:
        try:
            resp = self.model.generate_content(parts)
            return (resp.text or "").strip()
        except Exception as e:  # noqa: BLE001
            msg = str(e).lower()
            if any(k in msg for k in ["quota", "429", "resource_exhausted", "rate limit", "exhausted"]):
                raise QuotaError(str(e))
            raise

    # --- 1) İnsansı, kişiye özel DM üret ---
    def generate_dm(self, creator: dict, lang: str, product_pitch: str, learned_tips: str = "") -> str:
        """Creator'ın bio/niş/diline göre gerçekten insan gibi DM üretir."""
        lang_names = {"tr": "Turkish", "en": "English", "es": "Spanish",
                      "de": "German", "fr": "French", "ar": "Arabic"}
        lang_name = lang_names.get(lang, "English")
        name = creator.get("nickname") or creator.get("username", "")
        bio = creator.get("bio", "")
        followers = creator.get("followers", 0)

        prompt = f"""You are a real 16-year-old founder reaching out to a TikTok creator by DM.
Write ONE short, genuinely human DM in {lang_name}. It must NOT look AI-written.

CREATOR:
- name: {name}
- bio: {bio or '(empty)'}
- followers: {followers}
- niche/language: {lang_name}

WHAT I'M OFFERING (weave in naturally, do not hard-sell):
{product_pitch}

RULES (obey exactly):
- Max 3 short sentences. Texting a person, not announcing a product.
- Lowercase where natural, casual, a little raw. Use at most ONE emoji.
- Reference something real about THEM from their bio/niche if possible (personalize).
- NO link/URL in the text (TikTok blocks DMs with links). Instead say the link is in my bio.
- No corporate words, no "unlock/elevate/game-changer", no perfect symmetry.
- Sound like a real teenager who made a tool and wants honest feedback.
{('- Apply these learnings from what got replies before: ' + learned_tips) if learned_tips else ''}

Output ONLY the DM text, nothing else."""
        return self._generate(prompt)

    # --- 2) Gören AI: profil ekran görüntüsü analizi ---
    def analyze_profile(self, image_bytes: bytes, mime: str = "image/png") -> dict:
        """Profil ekran görüntüsünü 'görerek' analiz eder.
        Döner: {niche, tone, captions_weak(bool), fit_score(0-100), approach}
        """
        prompt = """Look at this TikTok profile screenshot as a growth expert.
Return STRICT JSON only, no markdown, with keys:
{"niche": str, "tone": str, "captions_weak": true/false,
 "fit_score": 0-100 (how good a fit for a caption-writing tool; weak captions = higher),
 "approach": one short sentence on how to pitch a caption tool to them}"""
        img_part = {"mime_type": mime, "data": image_bytes}
        raw = self._generate([prompt, img_part])
        return _safe_json(raw, default={
            "niche": "", "tone": "", "captions_weak": False, "fit_score": 50, "approach": ""
        })

    # --- 3) Gelen yanıtı analiz et ---
    def analyze_reply(self, dm_sent: str, reply_text: str, lang: str = "tr") -> dict:
        """Gelen cevabı sınıflandırır.
        Döner: {sentiment: pos/neu/neg, category: interested/question/not_interested/spammy,
                suggested_reply: str}
        """
        prompt = f"""A creator replied to my outreach DM. Classify it and draft a natural reply.
MY DM: {dm_sent}
THEIR REPLY: {reply_text}

Return STRICT JSON only:
{{"sentiment": "pos"|"neu"|"neg",
  "category": "interested"|"question"|"not_interested"|"spammy",
  "suggested_reply": "a short, human reply in the same language as their reply"}}"""
        raw = self._generate(prompt)
        return _safe_json(raw, default={
            "sentiment": "neu", "category": "question", "suggested_reply": ""
        })

    # --- 4) Geçmiş yanıtlardan öğren ---
    def learn_from_stats(self, samples: List[dict]) -> str:
        """samples: [{message, replied(bool), sentiment}] -> kısa strateji ipuçları.
        Bir sonraki DM üretiminde generate_dm(learned_tips=...) olarak kullanılır.
        """
        if not samples:
            return ""
        compact = [
            {"m": (s.get("message", "")[:200]), "replied": bool(s.get("replied")),
             "sent": s.get("sentiment", "")}
            for s in samples[:60]
        ]
        prompt = f"""Here are past outreach DMs and whether they got a reply.
Data (JSON): {json.dumps(compact, ensure_ascii=False)}

In 2-3 short bullet-like tips (one line each, no markdown), tell me what wording,
length, or angle correlates with MORE replies. Be specific and actionable so I can
write better DMs next time. Output only the tips."""
        try:
            return self._generate(prompt)
        except QuotaError:
            raise
        except Exception:
            return ""


def _safe_json(raw: str, default: dict) -> dict:
    if not raw:
        return default
    s = raw.strip()
    # ```json ... ``` sarmalını temizle
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
    # İlk { ile son } arasını al
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
