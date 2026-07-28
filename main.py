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
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: 'Inter', sans-serif; 
            background: linear-gradient(135deg, #2b5876, #4e4376); 
            height: 100vh; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
        }
        .telefon-ekrani { 
            width: 100%; 
            max-width: 400px; 
            height: 90vh; 
            background: #f4f4f8; 
            border-radius: 30px; 
            box-shadow: 0 20px 50px rgba(0,0,0,0.5); 
            display: flex; 
            flex-direction: column; 
            overflow: hidden; 
            border: 8px solid #333;
        }
        .ust-bilgi { 
            background: #ffffff; 
            padding: 20px; 
            text-align: center; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.05); 
            z-index: 10;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .profil-resmi {
            width: 50px;
            height: 50px;
            background: linear-gradient(135deg, #00C9FF 0%, #92FE9D 100%);
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 24px;
            margin-bottom: 5px;
        }
        .ust-bilgi h2 { font-size: 1.1rem; color: #111; font-weight: 600; }
        .durum { font-size: 0.8rem; color: #4caf50; font-weight: 500; }
        
        #chatbox { 
            flex: 1; 
            padding: 20px; 
            overflow-y: auto; 
            display: flex; 
            flex-direction: column; 
            gap: 15px; 
            background: #e5ddd5; 
        }
        .mesaj-kutusu { display: flex; flex-direction: column; max-width: 85%; }
        .sen { align-self: flex-end; }
        .sen .balon { 
            background: #007aff; 
            color: white; 
            border-radius: 18px 18px 4px 18px; 
            padding: 12px 16px; 
            font-size: 0.95rem;
            line-height: 1.4;
            box-shadow: 0 1px 2px rgba(0,0,0,0.1); 
        }
        .bot { align-self: flex-start; }
        .bot .balon { 
            background: #ffffff; 
            color: #333; 
            border-radius: 18px 18px 18px 4px; 
            padding: 12px 16px; 
            font-size: 0.95rem;
            line-height: 1.4;
            box-shadow: 0 1px 2px rgba(0,0,0,0.1); 
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
            border: 1px solid #ddd; 
            border-radius: 30px; 
            outline: none; 
            font-size: 0.95rem; 
            background: #f9f9f9; 
            transition: 0.3s;
        }
        input:focus { border-color: #007aff; background: #fff; }
        button { 
            background: #007aff; 
            color: white; 
            border: none; 
            border-radius: 50%; 
            width: 45px; 
            height: 45px; 
            cursor: pointer; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            transition: 0.2s; 
        }
        button:hover { background: #005bb5; transform: scale(1.05); }
        button svg { width: 20px; height: 20px; fill: white; margin-left: 3px; }
        
        .yaziyor { font-style: italic; color: #888; font-size: 0.85rem; padding-left: 5px; }
    </style>
</head>
<body>
    <div class="telefon-ekrani">
        <div class="ust-bilgi">
            <div class="profil-resmi">🤖</div>
            <h2>Emo AI</h2>
            <span class="durum">Çevrimiçi</span>
        </div>
        
        <div id="chatbox">
            <div class="mesaj-kutusu bot">
                <div class="balon">Merhaba! Size nasıl yardımcı olabilirim?</div>
            </div>
        </div>
        
        <div class="input-alani">
            <input type="text" id="userInput" placeholder="Mesaj yaz..." onkeypress="if(event.key === 'Enter') soruSor()">
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
            chatbox.innerHTML += `<div id="${loadingId}" class="mesaj-kutusu bot"><div class="yaziyor">Emo AI düşünüyor...</div></div>`;
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
                chatbox.innerHTML += `<div class="mesaj-kutusu bot"><div class="balon">${formatliCevap}</div></div>`;
                chatbox.scrollTop = chatbox.scrollHeight;
            })
            .catch(err => {
                document.getElementById(loadingId).remove();
                chatbox.innerHTML += `<div class="mesaj-kutusu bot"><div class="balon" style="color:red;">Bağlantı hatası oluştu.</div></div>`;
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
        uygun_modeller = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        basarili_cevap = None
        
        for model_adi in uygun_modeller:
            if "2.5-flash" in model_adi or "gemini-pro" == model_adi or "1.5-flash" == model_adi:
                continue
            try:
                # 1. HİÇBİR kural vermiyoruz. Kafasını karıştıracak kelime yok. Sadece mesajı atıyoruz.
                aktif_model = genai.GenerativeModel(model_adi)
                response = aktif_model.generate_content(kullanici_mesaji)
                
                ham_cevap = response.text.strip()
                
                # 2. PYTHON SANSÜRÜ: Eğer yine de inat edip İngilizce listeler yaparsa...
                if "User says:" in ham_cevap or "Constraint" in ham_cevap or "Role:" in ham_cevap or "Instruction:" in ham_cevap:
                    # Yazdığı destanı paragraflara ayır
                    paragraflar = ham_cevap.split('\n\n')
                    # SADECE en sondaki paragrafı (asıl cevabını) al
                    ham_cevap = paragraflar[-1].strip()
                    
                    # Eğer son paragrafta hala yıldız (*) varsa o satırları da at
                    if "*" in ham_cevap:
                        temiz_satirlar = [s for s in ham_cevap.split('\n') if not s.strip().startswith('*')]
                        if temiz_satirlar:
                            ham_cevap = temiz_satirlar[-1].strip()
                            
                # Tırnak işaretlerini vs. temizle
                basarili_cevap = ham_cevap.replace('"', '')
                break
                
            except Exception:
                continue
                
        if basarili_cevap:
            return basarili_cevap
        else:
            return "Şu an uygun bir model bulunamadı."
            
    except Exception as e:
        return f"Sistem hatası: {str(e)}"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
    
