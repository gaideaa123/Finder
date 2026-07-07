"""
CaptionAI Finder - AI Beyni (Groq, Llama 3.3 70B)
=================================================

- Kisiye ozel, TEK DILDE (kisinin gercek diline gore), PROFESYONEL, okunakli
  (paragraf bosluklu), yuksek tiklama getiren email + KONU uretir.
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
    "tr": "CaptionAI adinda kucuk bir arac yaptim: video konusunu yaziyorsun, saniyeler icinde 4 hazir, viral formatinda caption oneriyor.",
    "en": "I built a little tool called CaptionAI: you type your video topic and it gives 4 ready, viral-formula captions in seconds.",
    "es": "Hice una pequena herramienta llamada CaptionAI: escribes el tema de tu video y te da 4 captions listos, con formula viral, en segundos.",
    "de": "Ich habe ein kleines Tool namens CaptionAI gebaut: du gibst dein Videothema ein und bekommst in Sekunden 4 fertige Captions nach viraler Formel.",
    "fr": "J'ai cree un petit outil, CaptionAI : tu tapes le sujet de ta video et il te donne 4 legendes pretes, au format viral, en quelques secondes.",
    "ar": "\u0635\u0646\u0639\u062a \u0623\u062f\u0627\u0629 \u0635\u063a\u064a\u0631\u0629 \u0627\u0633\u0645\u0647\u0627 CaptionAI: \u062a\u0643\u062a\u0628 \u0645\u0648\u0636\u0648\u0639 \u0627\u0644\u0641\u064a\u062f\u064a\u0648 \u0648\u062a\u0639\u0637\u064a\u0643 4 \u0643\u0627\u0628\u0634\u0646\u0627\u062a \u062c\u0627\u0647\u0632\u0629 \u0628\u0635\u064a\u063a\u0629 \u0641\u0627\u064a\u0631\u0627\u0644 \u0628\u062b\u0648\u0627\u0646\u064a.",
}

# Daha guclu, merak uyandiran, spam gibi durmayan konu satirlari.
SUBJECTS = {
    "tr": ["{name}, videolarina dair kucuk bir fikir", "{name} icin hizli bir caption fikri",
           "{name}, icerigini cok begendim, bir onerim var", "caption'lari saniyeler icinde: {name} icin"],
    "en": ["{name}, a quick idea for your videos", "a caption idea I think you'll like, {name}",
           "{name}, really enjoy your content, one small idea", "captions in seconds, {name}?"],
    "es": ["{name}, una idea rapida para tus videos", "una idea de captions que te gustara, {name}",
           "{name}, me encanta tu contenido, una idea"],
    "de": ["{name}, eine kurze Idee fur deine Videos", "eine Caption-Idee, die dir gefallen konnte, {name}",
           "{name}, ich mag deinen Content, eine Idee"],
    "fr": ["{name}, une idee rapide pour tes videos", "une idee de legendes qui devrait te plaire, {name}",
           "{name}, j'adore ton contenu, une petite idee"],
    "ar": ["{name}\u060c \u0641\u0643\u0631\u0629 \u0633\u0631\u064a\u0639\u0629 \u0644\u0641\u064a\u062f\u064a\u0648\u0647\u0627\u062a\u0643", "\u0641\u0643\u0631\u0629 \u0643\u0627\u0628\u0634\u0646 \u0633\u062a\u0639\u062c\u0628\u0643 \u064a\u0627 {name}"],
}

# Temiz, PROFESYONEL, paragraf bosluklu fallback (AI bozuk cikarsa).
FALLBACK = {
    "tr": "Selam {name},\n\nVideolarini bir suredir takip ediyorum ve tarzini gercekten cok begeniyorum. Icerik ureticilerin en cok vakit kaybettigi seylerden biri caption yazmak, en azindan benim icin oyleydi.\n\n16 yasindayim ve tek basima CaptionAI adinda kucuk bir arac gelistirdim: video konusunu yaziyorsun, saniyeler icinde 4 hazir, viral formatinda caption oneriyor.\n\nSana ozel hazirladim diyebilirim, cunku tam senin gibi duzenli ureten insanlar icin ise yariyor. Bir denersen fikrini gercekten cok merak ederim:\n{url}\n\nSevgiler,\nBir gelistirici :)",
    "en": "Hi {name},\n\nI've been following your videos for a while and I genuinely love your style. One of the things creators lose the most time on is writing captions, at least that was true for me.\n\nI'm 16 and I built a small tool on my own called CaptionAI: you type your video topic and it gives you 4 ready, viral-formula captions in seconds.\n\nI thought of you because it works best for consistent creators like you. If you give it a quick try, I'd really love your honest feedback:\n{url}\n\nBest,\nA fellow builder :)",
    "es": "Hola {name},\n\nSigo tus videos desde hace un tiempo y de verdad me encanta tu estilo. Una de las cosas en las que los creadores pierden mas tiempo es escribir captions, al menos asi era para mi.\n\nTengo 16 anos e hice una pequena herramienta yo solo, se llama CaptionAI: escribes el tema de tu video y te da 4 captions listos, con formula viral, en segundos.\n\nPense en ti porque funciona mejor con creadores constantes como tu. Si la pruebas, me encantaria tu opinion sincera:\n{url}\n\nUn saludo,\nUn creador como tu :)",
    "de": "Hallo {name},\n\nich verfolge deine Videos schon eine Weile und mag deinen Stil wirklich sehr. Eine der zeitraubendsten Sachen fur Creator ist das Schreiben von Captions, zumindest war das bei mir so.\n\nIch bin 16 und habe allein ein kleines Tool namens CaptionAI gebaut: du gibst dein Videothema ein und bekommst in Sekunden 4 fertige Captions nach viraler Formel.\n\nIch habe an dich gedacht, weil es bei konstanten Creators wie dir am besten funktioniert. Uber dein ehrliches Feedback wurde ich mich sehr freuen:\n{url}\n\nViele Grusse,\nEin Entwickler :)",
    "fr": "Bonjour {name},\n\nje suis tes videos depuis un moment et j'aime vraiment beaucoup ton style. L'une des choses qui prend le plus de temps aux createurs, c'est ecrire les legendes, en tout cas c'etait mon cas.\n\nJ'ai 16 ans et j'ai cree seul un petit outil, CaptionAI : tu tapes le sujet de ta video et il te donne 4 legendes pretes, au format viral, en quelques secondes.\n\nJ'ai pense a toi car ca marche mieux avec des createurs reguliers comme toi. Si tu l'essaies, ton avis sincere m'interesserait beaucoup :\n{url}\n\nBien a toi,\nUn createur comme toi :)",
    "ar": "\u0645\u0631\u062d\u0628\u0627 {name}\u060c\n\n\u0623\u062a\u0627\u0628\u0639 \u0641\u064a\u062f\u064a\u0648\u0647\u0627\u062a\u0643 \u0645\u0646\u0630 \u0641\u062a\u0631\u0629 \u0648\u0623\u062d\u0628 \u0623\u0633\u0644\u0648\u0628\u0643 \u062d\u0642\u0627. \u0645\u0646 \u0623\u0643\u062b\u0631 \u0627\u0644\u0623\u0634\u064a\u0627\u0621 \u0627\u0644\u062a\u064a \u062a\u0623\u062e\u0630 \u0648\u0642\u062a \u0627\u0644\u0635\u0646\u0627\u0639 \u0647\u064a \u0643\u062a\u0627\u0628\u0629 \u0627\u0644\u0643\u0627\u0628\u0634\u0646.\n\n\u0639\u0645\u0631\u064a 16 \u0648\u0635\u0646\u0639\u062a \u0623\u062f\u0627\u0629 \u0627\u0633\u0645\u0647\u0627 CaptionAI: \u062a\u0643\u062a\u0628 \u0645\u0648\u0636\u0648\u0639 \u0627\u0644\u0641\u064a\u062f\u064a\u0648 \u0648\u062a\u062d\u0635\u0644 \u0639\u0644\u0649 4 \u0643\u0627\u0628\u0634\u0646\u0627\u062a \u062c\u0627\u0647\u0632\u0629 \u0628\u062b\u0648\u0627\u0646\u064a.\n\n\u064a\u0647\u0645\u0646\u064a \u0631\u0623\u064a\u0643 \u0627\u0644\u0635\u0631\u064a\u062d \u0625\u0630\u0627 \u062c\u0631\u0628\u062a\u0647\u0627:\n{url}\n\n\u062a\u062d\u064a\u0627\u062a\u064a",
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

    def _chat(self, system: str, user: str, temperature: float = 0.6, max_tokens: int = 420) -> str:
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
        if len(t) < 40 or len(t) > 1400:
            return True
        if self._wrong_alphabet(t, lang):
            return True
        low = t.lower()
        bad = ["baglantiim kuruldu", "ba\u011flant\u0131\u0131m kuruldu", "seninle baglanti", "olarak seninle",
               "connected with you", "i connected with you", "as someone who", "baja blast",
               "here is", "here's a", "iste bir email", "subject:"]
        if any(b in low for b in bad):
            return True
        # ayni cumle tekrari
        parts = [p.strip() for p in re.split(r"[.!?\n]", t) if len(p.strip()) > 12]
        if len(parts) != len(set(p.lower() for p in parts)):
            return True
        return False

    def _tidy(self, text: str) -> str:
        t = (text or "").strip()
        if len(t) >= 2 and t[0] in "\"'" and t[-1] in "\"'":
            t = t[1:-1].strip()
        t = re.sub(r"[ \t]{2,}", " ", t)
        # tek satir aralarina paragraf boslugu koyma; ama 3+ bosluk satirini 2'ye indir
        t = re.sub(r"\n{3,}", "\n\n", t)
        return t.strip()

    def _ensure_spacing(self, text: str) -> str:
        """Model bloklari birlestirmisse (cift newline yoksa) cumleleri paragraflara boler."""
        if "\n\n" in text:
            return text
        # cumlelere ayir, 1-2 cumlelik paragraflar yap
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) <= 2:
            return text
        paras, buf = [], []
        for s in sentences:
            buf.append(s)
            if len(buf) >= 2:
                paras.append(" ".join(buf)); buf = []
        if buf:
            paras.append(" ".join(buf))
        return "\n\n".join(paras)

    def _proofread(self, text: str, lang: str) -> str:
        lang_name = LANG_NAMES.get(lang, "English")
        system = (f"You are a meticulous native {lang_name} editor. Fix ONLY spelling, grammar and "
                  f"awkward wording so it reads like a polished, professional but warm email. "
                  f"KEEP the paragraph breaks (blank lines) and overall length. Do not add or remove ideas. "
                  f"Return ONLY the corrected text in {lang_name}.")
        try:
            out = self._tidy(self._chat(system, text, 0.15, 420))
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
            f"You are a real 16-year-old solo developer writing a polished but warm, professional outreach "
            f"email ENTIRELY in {lang_name}. It must read like a thoughtful human wrote it, not a marketer. "
            f"NEVER use cliches, NEVER translate English phrases literally, NEVER repeat a sentence, NEVER add a subject line."
        )
        user = (
            f"Write ONE professional yet friendly outreach email in {lang_name} ONLY (no other language/alphabet).\n\n"
            f"FORMAT (very important for readability):\n"
            f"- Start with a short greeting line addressing {name} (e.g. the {lang_name} equivalent of 'Hi {name},').\n"
            f"- Then 3 short PARAGRAPHS, each separated by a BLANK LINE (double line break). Do not cram it into one block.\n"
            f"- End with a short sign-off line on its own.\n\n"
            f"CONTENT of the paragraphs:\n"
            f"1) A specific, genuine compliment about THIS creator + a relatable line that writing captions takes creators a lot of time.\n"
            f"2) Who you are (16, built it alone, humble) and this idea in your own words: {pitch}\n"
            f"3) A warm, low-pressure invitation to try it and share honest feedback, with the link on its own line: {url}\n\n"
            f"Creator name: {name}\nCreator bio: {bio or '(none)'}\n\n"
            f"Perfect {lang_name} grammar and spelling. Natural, confident, respectful tone. "
            f"Output ONLY the email (greeting + paragraphs + sign-off), nothing else."
            + (f"\nWhat gets more replies: {learned_tips}" if learned_tips else "")
        )
        try:
            out = self._tidy(self._chat(system, user, 0.6, 460))
        except QuotaError:
            raise
        except Exception:
            return self._clean_fallback(name, lang, url)
        if self._looks_broken(out, lang):
            return self._clean_fallback(name, lang, url)
        if url and url.lower() not in out.lower():
            out = out.rstrip(" .") + f"\n\n{url}"
        out = self._proofread(out, lang)
        if self._looks_broken(out, lang):
            return self._clean_fallback(name, lang, url)
        out = self._ensure_spacing(out)
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
