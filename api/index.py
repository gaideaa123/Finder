"""Vercel serverless entry - SADECE checker dashboard.

Neden sadece checker? Vercel serverless'tir: kalici process/disk yok, fonksiyon
saniyeler sonra olur. 7/24 arka planda donen email botu + SQLite Vercel'de
CALISMAZ (o Fly.io gibi always-on host'ta durur). Ama checker istek geldikce
calisan, durum tutmayan bir dashboard oldugu icin Vercel'e tam uyar.

Groq/Apify anahtarlarini Vercel env'ine (GROQ_KEYS / APIFY_TOKENS) girebilir ya da
acilan sayfaya elle yapistirabilirsin.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, redirect
from checker import checker_bp

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__, template_folder=os.path.join(_ROOT, "templates"))
app.register_blueprint(checker_bp)

@app.route("/")
def _root():
    return redirect("/checker")
