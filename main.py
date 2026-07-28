import os
from flask import Flask, request, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# Render'daki gizli API anahtarımızı alıyoruz
API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

# Arayüz: Okyanus Teması ve Balık Tasarımı
HTML_SAYFASI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bilgin Balık</title>
    <link href="https://fonts.googleapis.com/css2?family=Comic+Neue:wght@400;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            /* Çocuklar için daha sevimli bir font */
            font-family: 'Comic Neue', cursive, sans-serif; 
            /* Okyanus arka planı */
            background: linear-gradient(135deg, #00b4db, #0083b0); 
            height: 100vh; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
        }
        .telefon-ekrani { 
            width: 100%; 
            max-width: 400px; 
            height: 90vh; 
            background: #e0f7fa; /* Açık su mavisi */
            border-radius: 30px; 
            box-shadow: 0 20px 50px rgba(0,0,0,0.5); 
            display: flex; 
            flex-direction: column; 
            overflow: hidden; 
            border: 8px solid #ffffff;
        }
        .ust-bilgi { 
            background: #0083b0; 
            padding: 15px; 
            text-align: center; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
            z-index: 10;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .profil-resmi {
            width: 60px;
            height: 60px;
            background: #ffffff;
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 35px; /* Büyük balık emojisi */
            margin-bottom: 5px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        .ust-bilgi h2 { font-size: 1.4rem; color: #ffffff; font-weight: 700; letter-spacing: 1px; }
        .durum { font-size: 0.9rem; color: #b2ebf2; font-weight: 700; }
        
        #chatbox { 
            flex: 1; 
            padding: 20px; 
            overflow-y: auto; 
            display: flex; 
            flex-direction: column; 
            gap: 15px; 
            background: url('https://www.transparenttextures.com/patterns/cubes.png'), #e0f7fa; 
        }
        .mesaj-kutusu { display: flex; flex-direction: column; max-width: 85%; }
        .sen { align-self: flex-end; }
        .sen .balon { 
            background: #ffb74d; /* Çocuk mesajı turuncu */
            color: #333; 
            border-radius: 20px 20px 4px 20px; 
            padding: 12px 16px; 
            font-size: 1.1rem;
            font-weight: 700;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1); 
        }
        .bot { align-self: flex-start; }
        .bot .balon { 
            background: #ffffff; 
            color: #006064; 
            border-radius: 20px 20px 20px 4px; 
            padding: 12px 16px; 
            font-size: 1.1rem;
            font-weight: 700;
            line-height: 1.4;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1); 
            border: 2px solid #80deea;
        }
        
        .input-alani { 
            display: flex; 
            padding: 15px; 
            background: #ffffff; 
            align-items: center;
            gap: 10px;
        }
        input { 
            flex: 1; 
            padding: 14px 20px; 
            border: 2px solid #80deea; 
            border-radius: 30px; 
            outline: none; 
            font-size: 1rem; 
            font-family: 'Comic Neue', cursive;
            font-weight: 700;
            background: #f9f9f9; 
            transition: 0.3s;
        }
        input:focus { border-color: #0083b0; background: #fff; }
        button { 
            background: #0083b0; 
            color: white; 
            border: none; 
            border-radius: 50%; 
            width: 50px; 
            height: 50px; 
            cursor: pointer; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            transition: 0.2s; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        }
        button:hover { background: #0056b3; transform: scale(1.05); }
        button svg { width: 24px; height: 24px; fill: white; margin-left: 2px; }
        
        .yaziyor { font-style: italic; color: #0083b0; font-size: 0.9rem; padding-left: 5px; font-weight: 700;}
    </style>
</head>
<body>
    <div class="telefon-ekrani">
        <div class="ust-bilgi">
            <div class="profil-resmi">🐠</div>
            <h2>Bilgin Balık</h2>
            <span class="durum">Sularda Yüzüyor 🫧</span>
        </div>
        
        <div id="chatbox">
            <div class="mesaj-kutusu bot">
                <div class="balon">Gluk gluk! Merhaba küçük dostum! 🫧 Ben Bilgin Balık. Suyun altından sana yardımcı olmak için geldim. Bana ne sormak istersin? 🐟</div>
            </div>
        </div>
        
        <div class="input-alani">
            <input type="text" id="userInput" placeholder="Balığa soru sor..." onkeypress="if(event.key === 'Enter') soruSor()">
            <button onclick="soruSor()">
                <svg viewBox="0 0 24 24"><path d="M2,21L23,12L2,3V10L17,12L2,14V21Z"></path></svg>
            </button>
        </div>
    </div>

    <script>
        function soruSor() {
            let inputElement = document.getElementById("userInput");
            let userText = inputElement.value.trim();
            if (userText === "") return;

            let chatbox = document.getElementById("chatbox");
            
            chatbox.innerHTML += `<div class="mesaj-kutusu sen"><div class="balon">${userText}</div></div>`;
            inputElement.value = "";
            chatbox.scrollTop = chatbox.scrollHeight;

            let loadingId = "loading-" + Date.now();
            chatbox.innerHTML += `<div id="${loadingId}" class="mesaj-kutusu bot"><div class="yaziyor">Bilgin Balık baloncuklar çıkarıyor... 🫧🫧</div></div>`;
            chatbox.scrollTop = chatbox.scrollHeight;

            fetch('/sor', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: 'mesaj=' + encodeURIComponent(userText)
            })
            .then(response => response.text())
            .then(data => {
                document.getElementById(loadingId).remove();
                // Basit kalınlaştırma ve alt satıra geçme ayarları
                let formatliCevap = data.replace(/\\n/g, '<br>').replace(/\\*\\*(.*?)\\*\\*/g, '<b>$1</b>');
                chatbox.innerHTML += `<div class="mesaj-kutusu bot"><div class="balon">${formatliCevap}</div></div>`;
                chatbox.scrollTop = chatbox.scrollHeight;
            })
            .catch(err => {
                document.getElementById(loadingId).remove();
                chatbox.innerHTML += `<div class="mesaj-kutusu bot"><div class="balon" style="color:red;">Olamaz! Denizanası kabloları ısırdı, tekrar dener misin? 🐙</div></div>`;
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
        
        # Balık karakterine bürünmesi için arka planda yapay zekaya gizli emir veriyoruz:
        cocuk_talimati = f"""Sen okyanusta yaşayan çok sevimli, eğlenceli ve akıllı 'Bilgin Balık'sın.
        Karşında sana soru soran küçük bir çocuk var.
        Kurallar:
        1. Çocuğa anlayabileceği çok basit, tatlı ve kısa cümlelerle cevap ver.
        2. Arada 'Gluk gluk', 'Şıp şıp' gibi balık sesleri kullan ve bol bol 🐠, 🫧, 🐟 gibi emojiler koy.
        3. Asla robot olduğunu veya yapay zeka olduğunu söyleme, sen gerçek bir balıksın.
        4. Kesinlikle iç sesini, İngilizce analizlerini (User says, Role vb.) yazma, sadece çocuğa cevap ver.
        
        Çocuğun sorusu: {kullanici_mesaji}"""
        
        # 404 Hatasını çözen sağlam model (gemini-pro)
        try:
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(cocuk_talimati)
            return response.text.strip()
        except Exception as model_hata:
            return f"Akvaryumda küçük bir sorun var: {str(model_hata)}"
            
    except Exception as e:
        return f"Sistem hatası: {str(e)}"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
    
