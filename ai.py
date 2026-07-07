"""
CaptionAI Finder - AI Beyni (Groq, Llama 3.3 70B)
=================================================

- Kisiye ozel, TEK DILDE (kisinin gercek diline gore), dogal, HATASIZ,
  yuksek tiklama getirecek email + KONU uretir.
- Bozuk cikti (dil karisimi, sacma calque, tekrar, yanlis alfabe) reddedilir.
"""

import json
import random
import re
from typing import List

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"

CJK_RE = re.compile(r"[\u3000-\u9fff\u3040-\u30ff\uac00-\ud7af]")
ARABIC_RE = re.compile(r"[\u0600-\u06ff]")

class QuotaError(Exception):
    """Tum key'ler tukendi/kota bitti."""

LANG_NAMES = {"tr": "Turkish", "en": "English", "es": "Spanish", "de": "German", "fr": "French", "ar": "Arabic"}

PITCH = {
    "tr": "CaptionAI adinda kucuk bir arac yaptim: video konusunu yaziyorsun, saniyeler icinde hazir caption oneriyor.",
    "en": "I built a little tool called CaptionAI: you type your video topic and it gives ready-to-post captions in seconds.",
    "es": "Hice una pequena herramienta llamada CaptionAI: escribes el tema de tu video y te da captions listos en segundos.",
    "de": "Ich habe ein kleines Tool namens CaptionAI gebaut: du gibst dein Videothema ein und bekommst in Sekunden fertige Captions.",
    "fr": "J'ai cree un petit outil, CaptionAI : tu tapes le sujet de ta video et il te donne des legendes pretes en quelques secondes.",
    "ar": "\u0635\u0646\u0639\u062a \u0623\u062f\u0627\u0629 \u0635\u063a\u064a\u0631\u0629 \u0627\u0633\u0645\u0647\u0627 CaptionAI: \u062a\u0643\u062a\u0628 \u0645\u0648\u0636\u0648\u0639 \u0627\u0644\u0641\u064a\u062f\u064a\u0648 \u0648\u062a\u0639\u0637\u064a\u0643 \u0643\u0627\u0628\u0634\u0646\u0627\u062a \u062c\u0627\u0647\u0632\u0629 \u0628\u062b\u0648\u0627\u0646\u064a.",
}

SUBJECTS = {
    "tr": ["{name}, videolarin icin kucuk bir fikir", "{name} caption konusunda ufak bir sey", "{name}, icerigin cok iyi, bir onerim var"],
    "en": ["{name}, a small idea for your videos", "quick caption idea for you {name}", "{name}, love your content, one idea"],
    "es": ["{name}, una pequena idea para tus videos", "idea rapida de captions para ti {name}"],
    "de": ["{name}, eine kleine Idee fur deine Videos", "kurze Caption-Idee fur dich {name}"],
    "fr": ["{name}, une petite idee pour tes videos", "petite idee de legendes pour toi {name}"],
    "ar": ["{name}\u060c \u0641\u0643\u0631\u0629 \u0635\u063a\u064a\u0631\u0629 \u0644\u0641\u064a\u062f\u064a\u0648\u0647\u0627\u062a\u0643"],
}

FALLBACK = {
    "tr": "Selam {name}, videolarini bir suredir takip ediyorum ve tarzini gercekten begeniyorum. 16 yasindayim ve tek basima CaptionAI adinda kucuk bir arac gelistirdim: video konusunu yaziyorsun, saniyeler icinde 4 hazir caption oneriyor. Caption yazmak beni hep zorladigi icin yaptim. Denersen fikrini cok merak ederim: {url}",
    "en": "Hey {name}, I've been following your videos for a while and I really like your style. I'm 16 and I built a little tool on my own called CaptionAI: you type your video topic and it gives 4 ready captions in seconds. I made it because writing captions always slowed me down. Would love your honest take if you try it: {url}",
    "es": "Hola {name}, sigo tus videos desde hace un tiempo y me encanta tu estilo. Tengo 16 anos e hice una pequena herramienta llamada CaptionAI: escribes el tema de tu video y te da 4 captions listos en segundos. La cree porque escribir captions siempre me costaba. Me encantaria tu opinion si la pruebas: {url}",
    "de": "Hey {name}, ich verfolge deine Videos schon eine Weile und mag deinen Stil sehr. Ich bin 16 und habe allein ein kleines Tool namens CaptionAI gebaut: du gibst dein Videothema ein und bekommst in Sekunden 4 fertige Captions. Ich habe es gemacht, weil mich das Schreiben von Captions immer aufgehalten hat. Uber dein ehrliches Feedback wurde ich mich freuen: {url}",
    "fr": "Hey {name}, je suis tes videos depuis un moment et j'aime beaucoup ton style. J'ai 16 ans et j'ai cree seul un petit outil appele CaptionAI : tu tapes le sujet de ta video et il te donne 4 legendes pretes en quelques secondes. Je l'ai fait parce qu'ecrire les legendes me ralentissait. Ton avis honnete m'interesserait si tu l'essaies : {url}",
    "ar": "\u0645\u0631\u062d\u0628\u0627 {name}\u060c \u0623\u062a\u0627\u0628\u0639 \u0641\u064a\u062f\u064a\u0648\u0647\u0627\u062a\u0643 \u0648\u0623\u062d\u0628 \u0623\u0633\u0644\u0648\u0628\u0643. \u0639\u0645\u0631\u064a 16 \u0648\u0635\u0646\u0639\u062a \u0623\u062f\u0627\u0629 \u0627\u0633\u0645\u0647\u0627 CaptionAI: \u062a\u0643\u062a\u0628 \u0645\u0648\u0636\u0648\u0639 \u0627\u0644\u0641\u064a\u062f\u064a\u0648 \u0648\u062a\u062d\u0635\u0644 \u0639\u0644\u0649 4 \u0643\u0627\u0628\u0634\u0646\u0627\u062a \u062c\u0627\u0647\u0632\u0629 \u0628\u062b\u0648\u0627\u0646\u064a. \u064a\u0647\u0645\u0646\u064a \u0631\u0623\u064a\u0643: {url}",
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

    def _chat(self, system: str, user: str, temperature: float = 0.6, max_tokens: int = 320) -> str:
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
            return "ok" in self._chat("You are a test.", "Reply with just: OK", 0, 5).lower()
        except QuotaError:
            raise
        except Exception:
            return False

    def _wrong_alphabet(self, text: str, lang: str) -> bool:
        if CJK_RE.search(text):
            return True
        if lang != "ar" and ARABIC_RE.search(text):
            return True
        if lang == "ar" and not ARABIC_RE.search(text):
            return True
        return False

    def _looks_broken(self, text: str, lang: str) -> bool:
        t = (text or "").strip()
        if len(t) < 25 or len(t) > 900:
            return True
        if self._wrong_alphabet(t, lang):
            return True
        low = t.lower()
        bad = ["baglantiim kuruldu", "ba\u011flant\u0131\u0131m kuruldu", "seninle baglanti", "olarak seninle",
               "connected with you", "i connected with you", "as someone who", "baja blast"]
        if any(b in low for b in bad):
            return True
        parts = [p.strip() for p in re.split(r"[.!?\n]", t) if len(p.strip()) > 12]
        if len(parts) != len(set(p.lower() for p in parts)):
            return True
        return False

    def _tidy(self, text: str) -> str:
        t = (text or "").strip()
        if len(t) >= 2 and t[0] in "\"'" and t[-1] in "\"'":
            t = t[1:-1].strip()
        t = re.sub(r"[ \t]{2,}", " ", t)
        t = re.sub(r"\n{3,}", "\n\n", t)
        return t.strip()

    def _proofread(self, text: str, lang: str) -> str:
        lang_name = LANG_NAMES.get(lang, "English")
        system = (f"You are a meticulous native {lang_name} proofreader. Fix ONLY spelling, grammar and "
                  f"awkward word choices so it reads like a real native speaker wrote it. Keep the same meaning, "
                  f"casual tone and length. Do not add anything. Return ONLY the corrected text in {lang_name}.")
        try:
            out = self._tidy(self._chat(system, text, 0.1, 320))
            return out if out and not self._wrong_alphabet(out, lang) else text
        except QuotaError:
            raise
        except Exception:
            return text

    def _clean_fallback(self, name, lang, url) -> str:
        base = FALLBACK.get(lang, FALLBACK["en"])
        return base.replace("{name}", name or "").replace("{url}", url or "")

    def make_subject(self, creator, lang) -> str:
        if lang not in LANG_NAMES:
            lang = "en"
        name = creator.get("nickname") or creator.get("username", "")
        return random.choice(SUBJECTS.get(lang, SUBJECTS["en"])).replace("{name}", name).strip()

    def generate_dm(self, creator, lang, product_pitch="", learned_tips="", link_url="", channel="email") -> str:
        if lang not in LANG_NAMES:
            lang = "en"
        name = creator.get("nickname") or creator.get("username", "")
        bio = (creator.get("bio", "") or "").strip()
        lang_name = LANG_NAMES[lang]
        pitch = PITCH.get(lang, PITCH["en"])
        url = link_url or "thecaptionai.com"

        system = (
            f"You write short, warm, high-converting outreach emails, ENTIRELY in {lang_name}. "
            f"You are a real 16-year-old solo developer, not a marketer. Write like a human texting a creator you admire. "
            f"NEVER use marketing cliches, NEVER translate English phrases literally, NEVER repeat a sentence."
        )
        user = (
            f"Write ONE short outreach email body in {lang_name} ONLY (no other language or alphabet).\n\n"
            f"Goal: make the creator curious enough to click the link. Sound genuine, not salesy.\n"
            f"Flow (4-6 short sentences):\n"
            f"1) A specific, genuine compliment about THIS creator (use their vibe/niche if the bio hints it).\n"
            f"2) One honest line that writing captions used to slow me down.\n"
            f"3) This idea in your own words: {pitch}\n"
            f"4) A light, low-pressure ask to try it and share honest feedback. Include this link once: {url}\n\n"
            f"I am 16 and built it alone (mention humbly, once).\n"
            f"Creator name: {name}\nCreator bio: {bio or '(none)'}\n\n"
            f"Perfect {lang_name} grammar/spelling. No subject line. No 'Dear'. No bullet points. "
            f"No emoji at the start. Output ONLY the email body."
            + (f"\nWhat gets more replies: {learned_tips}" if learned_tips else "")
        )
        try:
            out = self._tidy(self._chat(system, user, 0.6, 340))
        except QuotaError:
            raise
        except Exception:
            return self._clean_fallback(name, lang, url)
        if self._looks_broken(out, lang):
            return self._clean_fallback(name, lang, url)
        if url and url.lower() not in out.lower():
            out = out.rstrip(" .") + f": {url}"
        out = self._proofread(out, lang)
        if self._looks_broken(out, lang):
            return self._clean_fallback(name, lang, url)
        return out

    def generate_hashtags(self, lang="tr", countries=None, niche_hint="", count=12) -> List[str]:
        lang_name = LANG_NAMES.get(lang, "English")
        loc = ", ".join(countries) if countries else lang_name
        system = ("You are a TikTok growth expert. Output ONLY a JSON array of hashtag strings, "
                  "no '#', lowercase, no spaces, no explanation.")
        user = (f"Give {count} TikTok hashtags in {lang_name} (market: {loc}) to find CONTENT CREATORS "
                f"who post a lot but likely struggle with captions (ideal for an AI caption tool). "
                f"Niches: food, daily vlog, fashion/GRWM, skincare, fitness, travel, books, small business/sellers. "
                + (f"Focus: {niche_hint}. " if niche_hint else "")
                + 'Return ONLY a JSON array, e.g. ["yemektarifi","gunlukvlog"].')
        try:
            raw = self._chat(system, user, 0.6, 250)
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
        return _safe_json(self._chat("Return only strict JSON.", user, 0.5, 200),
                          {"sentiment": "neu", "category": "question", "suggested_reply": ""})

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
