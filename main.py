import os
import google.generativeai as genai
from flask import Flask, jsonify, request

# Güvenlik güncellemesi: API Key artık kodun içinde açıkça yazmıyor!
# Render üzerindeki "Environment Variables" kısmından gizlice çekecek.
API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=API_KEY)

# %90+ Doğruluk ve Karakter Ayarı
instruction = """
Sen uzman ve son derece güvenilir bir yapay zeka asistansın.
KURALLARIN:
1. Sadece %100 emin olduğun kesin gerçekleri söyle.
2. Emin olmadığın veya bilmediğin bir konu sorulursa asla uydurma, 'Bu konuda kesin bir bilgim yok' de.
3. Cevapların net, doğru ve anlaşılır olsun.
"""

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash", system_instruction=instruction
)

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "Yapay zekan 7/24 aktif, güvenli ve çalışıyor!"

@app.route("/sor", methods=["POST"])
def sor():
    data = request.json
    kullanici_sorusu = data.get("soru", "")
    if not kullanici_sorusu:
        return jsonify({"hata": "Lutfen bir soru sorun."}), 400

    cevap = model.generate_content(kullanici_sorusu)
    return jsonify({"cevap": cevap.text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
  
