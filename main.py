import os
from flask import Flask, request, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# Render'daki gizli API anahtarımızı alıyoruz
API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

# Arayüz için HTML, CSS ve JavaScript kodumuz
HTML_SAYFASI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Emo AI</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; display: flex; justify-content: center; padding: 20px; }
        .chat-container { width: 100%; max-width: 600px; background: white; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); padding: 20px; }
        h2 { text-align: center; color: #333; }
        #chatbox { height: 400px; overflow-y: auto; border: 1px solid #ddd; border-radius: 5px; padding: 15px; margin-bottom: 15px; background: #fafafa; }
        .mesaj { margin-bottom: 10px; padding: 10px; border-radius: 8px; max-width: 80%; line-height: 1.4; }
        .sen { background-color: #d1e7dd; margin-left: auto; text-align: right; }
        .bot { background-color: #e2e3e5; margin-right: auto; text-align: left; }
        .input-area { display: flex; gap: 10px; }
        input { flex: 1; padding: 10px; border: 1px solid #ccc; border-radius: 5px; outline: none; font-size: 16px; }
        button { padding: 10px 20px; background-color: #0d6efd; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
        button:hover { background-color: #0b5ed7; }
    </style>
</head>
<body>
    <div class="chat-container">
        <h2>Emo AI ✨</h2>
        <div id="chatbox">
            <div class="mesaj bot"><b>Emo AI:</b> <br>Merhaba! Ben hazırım, bana istediğini sorabilirsin.</div>
        </div>
        <div class="input-area">
            <input type="text" id="userInput" placeholder="Mesajını yaz..." onkeypress="if(event.key === 'Enter') soruSor()">
            <button onclick="soruSor()">Gönder</button>
        </div>
    </div>

    <script>
        function soruSor() {
            let inputElement = document.getElementById("userInput");
            let userText = inputElement.value.trim();
            if (userText === "") return;

            let chatbox = document.getElementById("chatbox");
            
            chatbox.innerHTML += `<div class="mesaj sen"><b>Sen:</b> <br>${userText}</div>`;
            inputElement.value = "";
            chatbox.scrollTop = chatbox.scrollHeight;

            let loadingId = "loading-" + Date.now();
            chatbox.innerHTML += `<div id="${loadingId}" class="mesaj bot"><i>Emo AI düşünüyor... 🧠</i></div>`;
            chatbox.scrollTop = chatbox.scrollHeight;

            fetch('/sor', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: 'mesaj=' + encodeURIComponent(userText)
            })
            .then(response => response.text())
            .then(data => {
                document.getElementById(loadingId).remove();
                let formatliCevap = data.replace(/\\n/g, '<br>').replace(/\\*\\*(.*?)\\*\\*/g, '<b>$1</b>');
                chatbox.innerHTML += `<div class="mesaj bot"><b>Emo AI:</b> <br>${formatliCevap}</div>`;
                chatbox.scrollTop = chatbox.scrollHeight;
            })
            .catch(err => {
                document.getElementById(loadingId).remove();
                chatbox.innerHTML += `<div class="mesaj bot" style="color:red;"><b>Hata:</b> Bağlantı kurulamadı.</div>`;
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_SAYFASI)

@app.route('/sor', methods=['POST'])
def sor():
    try:
        kullanici_mesaji = request.form['mesaj']
        
        # API'nin desteklediği TÜM modelleri bul
        uygun_modeller = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        son_hata = ""
        basarili_cevap = None
        
        # Hepsini tek tek dene
        for model_adi in uygun_modeller:
            # Hata veren eski modelleri doğrudan pas geç
            if "2.5-flash" in model_adi or "gemini-pro" == model_adi or "1.5-flash" == model_adi:
                continue
                
            try:
                aktif_model = genai.GenerativeModel(model_adi)
                response = aktif_model.generate_content(kullanici_mesaji)
                basarili_cevap = response.text
                break # Çalışan modeli bulduk, döngüyü bitir!
            except Exception as e:
                son_hata = str(e)
                continue # Hata verirse pes etme, sıradaki modele geç
                
        # Eğer bir cevap bulabildiyse döndür
        if basarili_cevap:
            return basarili_cevap
        else:
            return f"Maalesef çalışan bir model bulunamadı. Son alınan hata: {son_hata} <br> Hesabındaki modeller şunlar: {', '.join(uygun_modeller)}"
            
    except Exception as e:
        return f"Genel bir hata oluştu: {str(e)}"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
