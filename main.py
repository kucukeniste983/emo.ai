import os
from flask import Flask, request, render_template_string
import google.generativeai as genai

app = Flask(__name__)

# Render'daki gizli API anahtarımızı alıyoruz
API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

# Tam Ekran Akvaryum Tasarımı (Balık konuşma animasyonlu)
HTML_SAYFASI = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dev Akvaryum - Bilgin Balık</title>
    <link href="https://fonts.googleapis.com/css2?family=Fredoka+One&family=Nunito:wght@700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: 'Nunito', sans-serif; 
            /* Akvaryum derinlik efekti */
            background: radial-gradient(circle at center, #00b4db 0%, #000428 100%);
            height: 100vh; 
            display: flex; 
            flex-direction: column;
            justify-content: flex-end; 
            align-items: center; 
            overflow: hidden;
            position: relative;
        }
        
        /* Arkadan çıkan su baloncukları */
        .baloncuk {
            position: absolute;
            bottom: -50px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 50%;
            border: 1px solid rgba(255, 255, 255, 0.5);
            animation: yukari-cik infinite ease-in;
        }
        @keyframes yukari-cik {
            0% { transform: translateY(0) scale(1); opacity: 1; }
            100% { transform: translateY(-100vh) scale(1.5); opacity: 0; }
        }

        .akvaryum-merkez {
            position: absolute;
            top: 40%;
            left: 50%;
            transform: translate(-50%, -50%);
            display: flex;
            flex-direction: column;
            align-items: center;
            z-index: 10;
        }

        /* Konuşma Balonu */
        .konusma-balonu {
            background: #ffffff;
            color: #004e92;
            padding: 20px 25px;
            border-radius: 30px;
            font-size: 1.3rem;
            max-width: 350px;
            text-align: center;
            box-shadow: 0 15px 25px rgba(0,0,0,0.3);
            margin-bottom: 30px;
            position: relative;
            font-family: 'Fredoka One', cursive;
            border: 4px solid #80deea;
        }
        .konusma-balonu::after {
            content: '';
            position: absolute;
            bottom: -20px;
            left: 50%;
            transform: translateX(-50%);
            border-width: 20px 20px 0;
            border-style: solid;
            border-color: #ffffff transparent transparent transparent;
        }
        .konusma-balonu::before {
            content: '';
            position: absolute;
            bottom: -26px;
            left: 50%;
            transform: translateX(-50%);
            border-width: 24px 24px 0;
            border-style: solid;
            border-color: #80deea transparent transparent transparent;
            z-index: -1;
        }

        /* Dev Balık */
        .balik {
            font-size: 160px; /* Balığı devasa yaptık */
            animation: yuzme 4s ease-in-out infinite;
            filter: drop-shadow(0 15px 15px rgba(0,0,0,0.4));
        }

        /* Ağzıyla Konuşma / Titreme Efekti */
        .balik.konusuyor {
            animation: yuzme 4s ease-in-out infinite, agiz-hareketi 0.25s infinite alternate !important;
        }

        @keyframes yuzme {
            0%, 100% { transform: translateY(0px) rotate(0deg); }
            50% { transform: translateY(-20px) rotate(3deg); }
        }
        
        @keyframes agiz-hareketi {
            0% { transform: scale(1) rotate(0deg) skewX(0deg); }
            100% { transform: scale(1.08) rotate(-5deg) skewX(-2deg); }
        }

        /* Alt kısımdaki soru sorma alanı */
        .input-alani { 
            display: flex; 
            padding: 20px; 
            background: rgba(255,255,255,0.15); 
            backdrop-filter: blur(10px);
            align-items: center;
            gap: 15px;
            width: 100%;
            max-width: 600px;
            border-radius: 40px 40px 0 0;
            z-index: 20;
            border-top: 2px solid rgba(255,255,255,0.3);
        }
        input { 
            flex: 1; 
            padding: 18px 25px; 
            border: none; 
            border-radius: 30px; 
            outline: none; 
            font-size: 1.1rem; 
            font-family: 'Nunito', sans-serif;
            font-weight: 700;
            box-shadow: inset 0 3px 5px rgba(0,0,0,0.1);
        }
        button { 
            background: #ffb74d; 
            color: #111; 
            border: none; 
            border-radius: 50%; 
            width: 60px; 
            height: 60px; 
            cursor: pointer; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            transition: 0.2s; 
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }
        button:hover { background: #ffa726; transform: scale(1.1); }
        button svg { width: 28px; height: 28px; fill: #111; margin-left: 2px; }
    </style>
</head>
<body>
    
    <!-- Arka plan baloncukları -->
    <div class="baloncuk" style="width: 20px; height: 20px; left: 10%; animation-duration: 4s;"></div>
    <div class="baloncuk" style="width: 30px; height: 30px; left: 30%; animation-duration: 6s; animation-delay: 1s"></div>
    <div class="baloncuk" style="width: 15px; height: 15px; left: 60%; animation-duration: 5s; animation-delay: 2s"></div>
    <div class="baloncuk" style="width: 25px; height: 25px; left: 80%; animation-duration: 7s; animation-delay: 0.5s"></div>

    <div class="akvaryum-merkez">
        <div id="konusmaBalonu" class="konusma-balonu">Gluk gluk! Ben Bilgin Balık! 🫧<br>Akvaryumuma hoş geldin, bana ne sormak istersin?</div>
        <div id="balik" class="balik">🐠</div>
    </div>
    
    <div class="input-alani">
        <input type="text" id="userInput" placeholder="Balığa bir soru sor..." onkeypress="if(event.key === 'Enter') soruSor()">
        <button onclick="soruSor()">
            <svg viewBox="0 0 24 24"><path d="M2,21L23,12L2,3V10L17,12L2,14V21Z"></path></svg>
        </button>
    </div>

    <script>
        function soruSor() {
            let inputElement = document.getElementById("userInput");
            let userText = inputElement.value.trim();
            if (userText === "") return;

            let balon = document.getElementById("konusmaBalonu");
            let balik = document.getElementById("balik");
            
            // Düşünme aşaması (Ağzı hareket ediyor)
            balon.innerHTML = "Hmm... Düşünüyorum... Gluk gluk... 🫧";
            balik.classList.add("konusuyor");
            inputElement.value = "";

            fetch('/sor', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: 'mesaj=' + encodeURIComponent(userText)
            })
            .then(response => response.text())
            .then(data => {
                // Cevap gelince ağzı hala oynamaya devam etsin (okuma süresi kadar)
                balon.innerHTML = data;
                
                // Cümlenin uzunluğuna göre ağzını oynatma süresini belirliyoruz
                let okumaSuresi = Math.min(data.length * 60, 5000); 
                
                // Önce temizle, sonra tekrar ekle ki animasyon baştan başlasın
                balik.classList.remove("konusuyor");
                void balik.offsetWidth; // CSS Trigger
                balik.classList.add("konusuyor");
                
                // Konuşma süresi bitince ağzı dursun
                setTimeout(() => {
                    balik.classList.remove("konusuyor");
                }, okumaSuresi);
            })
            .catch(err => {
                balik.classList.remove("konusuyor");
                balon.innerHTML = "Olamaz! Denizanası bağlantımı kesti. 🐙";
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
        
        # 404 HATASINI KESİN ÇÖZEN KOD: Google'a "bana açık olan modelleri ver" diyoruz.
        gecerli_modeller = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        if not gecerli_modeller:
            return "Okyanusta uygun balık bulunamadı! API key ayarlarını kontrol et."
            
        # Listeden, hesabına izni olan İLK MODELİ seçiyoruz (404 vermesi imkansız)
        secilen_model_adi = gecerli_modeller[0] 
        model = genai.GenerativeModel(secilen_model_adi)
        
        cocuk_talimati = f"""Sen dev akvaryumda yaşayan çok eğlenceli 'Bilgin Balık'sın.
        Kurallar:
        1. Çocuğa anlayabileceği çok kısa, tatlı cümlelerle cevap ver.
        2. Robot, yapay zeka olduğunu asla söyleme. Sen gerçek bir balıksın.
        
        Çocuğun sorusu: {kullanici_mesaji}"""
        
        response = model.generate_content(cocuk_talimati)
        ham_cevap = response.text.strip()
        
        # -- SENİN İSTEDİĞİN SANSÜR SİSTEMİ --
        # Model yine not tutar veya liste yaparsa, sadece sondaki asıl cevabı kesip alıyoruz.
        if "Role:" in ham_cevap or "User says:" in ham_cevap or "Intent" in ham_cevap:
            satirlar = ham_cevap.split('\\n')
            temiz_satirlar = [s for s in satirlar if s.strip() != "" and not s.strip().startswith('*')]
            if temiz_satirlar:
                ham_cevap = temiz_satirlar[-1].replace('"', '')
                
        return ham_cevap
        
    except Exception as e:
        return f"Balık biraz tıkandı: {str(e)}"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
    
