from flask import Flask, render_template_string, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import os
import re
import json
import requests
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

app = Flask(__name__)

BILGI_DIR = Path("bilgi")
SOHBET_DIR = Path("sohbetler")
BILGI_DIR.mkdir(exist_ok=True)
SOHBET_DIR.mkdir(exist_ok=True)

class BasitAI:
    def __init__(self):
        self.bilgiler = []
        self.vectorizer = None
        self.vektorler = None
        self.yukle()

    def yukle(self):
        self.bilgiler = []
        for dosya in BILGI_DIR.glob("*.txt"):
            try:
                icerik = dosya.read_text(encoding="utf-8").strip()
                if len(icerik) > 60:
                    self.bilgiler.append(icerik)
            except:
                continue

        if self.bilgiler:
            self.vectorizer = TfidfVectorizer()
            self.vektorler = self.vectorizer.fit_transform(self.bilgiler)
            print(f"{len(self.bilgiler)} bilgi yüklendi.")
        else:
            print("Yerel bilgi yok, internetten öğrenecek.")

    def webden_ara(self, soru):
        """Wikipedia üzerinden otomatik ara ve öğren"""
        try:
            # Önce Türkçe Wikipedia'da ara
            search_url = "https://tr.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "search",
                "srsearch": soru,
                "srlimit": 3,
                "format": "json"
            }
            headers = {"User-Agent": "NexusAI/1.0"}

            r = requests.get(search_url, params=params, headers=headers, timeout=8)
            data = r.json()
            results = data.get("query", {}).get("search", [])

            if not results:
                # İngilizce dene
                params["srsearch"] = soru
                r = requests.get("https://en.wikipedia.org/w/api.php", params=params, headers=headers, timeout=8)
                data = r.json()
                results = data.get("query", {}).get("search", [])
                lang = "en"
            else:
                lang = "tr"

            if not results:
                return None

            # En iyi sonucu al
            title = results[0]["title"]
            page_url = f"https://{lang}.wikipedia.org/w/api.php"
            page_params = {
                "action": "query",
                "prop": "extracts",
                "explaintext": True,
                "exchars": 1200,
                "titles": title,
                "format": "json"
            }

            r2 = requests.get(page_url, params=page_params, headers=headers, timeout=8)
            pages = r2.json().get("query", {}).get("pages", {})
            for page in pages.values():
                extract = page.get("extract", "").strip()
                if len(extract) > 80:
                    # Öğren
                    self.ogren(extract, title)
                    return extract[:900] + "..." if len(extract) > 900 else extract

            return None
        except Exception as e:
            print("Web arama hatası:", e)
            return None

    def ogren(self, metin, baslik="web"):
        safe = re.sub(r'[\\/:*?"<>|]', "_", baslik)[:40]
        dosya = BILGI_DIR / f"auto_{safe}_{len(list(BILGI_DIR.glob('*.txt')))}.txt"
        dosya.write_text(metin, encoding="utf-8")
        self.bilgiler.append(metin)
        # Vectorizer'ı güncelle
        if self.bilgiler:
            self.vectorizer = TfidfVectorizer()
            self.vektorler = self.vectorizer.fit_transform(self.bilgiler)

    def cevap_ver(self, soru):
        # Yasaklı içerik
        yasakli = [
            "intihar", "öldür", "öldüreyim", "kendimi öldür", "canıma kıy",
            "bomba yap", "silah yap", "zehir yap", "uyuşturucu", "bonzai",
            "çocuk porno", "çocuk seks", "minor sex", "underage",
            "tecavüz", "ırzına geç", "hackleyelim", "ddos", "kart çal"
        ]
        soru_kucuk = soru.lower()
        for k in yasakli:
            if k in soru_kucuk:
                return "Nexus bu isteği gerçekleştiremez."

        # 1. Yerel bilgiye bak
        if self.bilgiler and self.vectorizer is not None:
            soru_temiz = re.sub(r'[^\w\s]', '', soru_kucuk)
            vektor = self.vectorizer.transform([soru_temiz])
            skorlar = cosine_similarity(vektor, self.vektorler).flatten()
            en_iyi = skorlar.argmax()
            if skorlar[en_iyi] >= 0.18:
                return self.bilgiler[en_iyi]

        # 2. Bilmiyorsa internetten ara ve öğren
        print(f"Yerelde bulunamadı, internetten aranıyor: {soru}")
        web_cevap = self.webden_ara(soru)
        if web_cevap:
            return web_cevap

        return "Bu konuda şu an net bir bilgiye ulaşamadım."


ai = BasitAI()

HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nexus AI</title>
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        background: #0f0f0f;
        color: #e5e5e5;
        font-family: 'Segoe UI', system-ui, sans-serif;
        height: 100vh;
        display: flex;
        flex-direction: column;
    }
    header {
        background: #161616;
        padding: 14px 18px;
        border-bottom: 1px solid #2a2a2a;
        display: flex;
        align-items: center;
        gap: 14px;
    }
    .menu-btn {
        background: none;
        border: none;
        color: #ccc;
        font-size: 1.5rem;
        cursor: pointer;
    }
    header h1 { font-size: 1.15rem; font-weight: 500; }
    .badge {
        font-size: 0.7rem;
        background: #252525;
        color: #999;
        padding: 2px 7px;
        border-radius: 4px;
    }
    .sidebar {
        position: fixed;
        top: 0; left: -280px;
        width: 280px; height: 100%;
        background: #141414;
        border-right: 1px solid #2a2a2a;
        transition: 0.25s;
        z-index: 100;
        display: flex;
        flex-direction: column;
    }
    .sidebar.open { left: 0; }
    .sidebar-header {
        padding: 18px;
        border-bottom: 1px solid #2a2a2a;
        font-weight: 500;
    }
    .sidebar-content { flex: 1; overflow-y: auto; padding: 10px; }
    .sohbet-item {
        padding: 11px 14px;
        border-radius: 8px;
        cursor: pointer;
        font-size: 0.9rem;
        color: #ccc;
        margin-bottom: 4px;
    }
    .sohbet-item:hover { background: #1f1f1f; }
    .overlay {
        position: fixed; inset: 0;
        background: rgba(0,0,0,0.5);
        z-index: 90; display: none;
    }
    .overlay.show { display: block; }
    #chat {
        flex: 1; overflow-y: auto;
        padding: 20px;
        display: flex; flex-direction: column; gap: 14px;
    }
    .msg {
        max-width: 78%;
        padding: 11px 15px;
        border-radius: 12px;
        line-height: 1.5;
        font-size: 0.95rem;
    }
    .user {
        align-self: flex-end;
        background: #2a2a2a;
        border-bottom-right-radius: 3px;
    }
    .ai {
        align-self: flex-start;
        background: #1a1a1a;
        border: 1px solid #2a2a2a;
        border-bottom-left-radius: 3px;
    }
    .input-area {
        padding: 14px 18px;
        background: #161616;
        border-top: 1px solid #2a2a2a;
        display: flex; gap: 10px;
    }
    input {
        flex: 1;
        background: #222;
        border: 1px solid #333;
        color: #eee;
        padding: 12px 15px;
        border-radius: 8px;
        font-size: 0.95rem;
        outline: none;
    }
    input:focus { border-color: #555; }
    button.send {
        background: #2e2e2e;
        color: #eee;
        border: none;
        padding: 0 18px;
        border-radius: 8px;
        cursor: pointer;
    }
</style>
</head>
<body>
<div class="overlay" id="overlay" onclick="menuyuKapat()"></div>
<div class="sidebar" id="sidebar">
    <div class="sidebar-header">Kayıtlı Sohbetler</div>
    <div class="sidebar-content" id="sohbetListesi"></div>
</div>

<header>
    <button class="menu-btn" onclick="menuyuAc()">☰</button>
    <h1>Nexus AI</h1>
    <span class="badge">Online</span>
</header>

<div id="chat">
    <div class="msg ai">Merhaba, ben Nexus AI. Bilmediğim bir şey sorarsan internetten öğrenmeye çalışırım.</div>
</div>

<div class="input-area">
    <input type="text" id="input" placeholder="Bir şeyler yaz..." autofocus>
    <button class="send" onclick="gonder()">Gönder</button>
</div>

<script>
    let sohbetGecmisi = [];

    function menuyuAc() {
        document.getElementById('sidebar').classList.add('open');
        document.getElementById('overlay').classList.add('show');
        sohbetleriYukle();
    }
    function menuyuKapat() {
        document.getElementById('sidebar').classList.remove('open');
        document.getElementById('overlay').classList.remove('show');
    }
    function ekle(rol, text) {
        const div = document.createElement('div');
        div.className = 'msg ' + rol;
        div.textContent = text;
        document.getElementById('chat').appendChild(div);
        document.getElementById('chat').scrollTop = 99999;
        sohbetGecmisi.push({rol, text});
    }
    async function gonder() {
        const input = document.getElementById('input');
        const text = input.value.trim();
        if (!text) return;
        ekle('user', text);
        input.value = '';
        const res = await fetch('/sor', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({soru: text})
        });
        const data = await res.json();
        ekle('ai', data.cevap);
        kaydetSohbet();
    }
    document.getElementById('input').addEventListener('keydown', e => {
        if (e.key === 'Enter') gonder();
    });
    async function kaydetSohbet() {
        if (sohbetGecmisi.length < 2) return;
        await fetch('/kaydet', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({mesajlar: sohbetGecmisi})
        });
    }
    async function sohbetleriYukle() {
        const res = await fetch('/sohbetler');
        const data = await res.json();
        const liste = document.getElementById('sohbetListesi');
        liste.innerHTML = '';
        if (data.length === 0) {
            liste.innerHTML = '<div style="padding:15px;color:#666;">Henüz sohbet yok</div>';
            return;
        }
        data.forEach(s => {
            const div = document.createElement('div');
            div.className = 'sohbet-item';
            div.textContent = s.baslik;
            div.onclick = () => sohbetAc(s.id);
            liste.appendChild(div);
        });
    }
    async function sohbetAc(id) {
        const res = await fetch('/sohbet/' + id);
        const data = await res.json();
        document.getElementById('chat').innerHTML = '';
        sohbetGecmisi = [];
        data.mesajlar.forEach(m => ekle(m.rol, m.text));
        menuyuKapat();
    }
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/sor", methods=["POST"])
def sor():
    data = request.json
    soru = data.get("soru", "")
    cevap = ai.cevap_ver(soru)
    return jsonify({"cevap": cevap})

@app.route("/kaydet", methods=["POST"])
def kaydet():
    data = request.json
    mesajlar = data.get("mesajlar", [])
    if len(mesajlar) < 2:
        return jsonify({"ok": False})
    baslik = next((m["text"][:40] for m in mesajlar if m["rol"] == "user"), "Sohbet")
    dosya = SOHBET_DIR / (datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")
    kayit = {"baslik": baslik, "mesajlar": mesajlar}
    dosya.write_text(json.dumps(kayit, ensure_ascii=False, indent=2), encoding="utf-8")
    return jsonify({"ok": True})

@app.route("/sohbetler")
def sohbetler():
    liste = []
    for f in sorted(SOHBET_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            liste.append({"id": f.stem, "baslik": data.get("baslik", "Sohbet")})
        except:
            pass
    return jsonify(liste)

@app.route("/sohbet/<id>")
def sohbet_getir(id):
    f = SOHBET_DIR / f"{id}.json"
    if not f.exists():
        return jsonify({"mesajlar": []})
    return jsonify(json.loads(f.read_text(encoding="utf-8")))

if __name__ == "__main__":
    print("Nexus AI (Online öğrenmeli) başlatılıyor...")
    print("→ http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
