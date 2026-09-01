# 🧠 avenoxbeyin - Google Antigravity Kurulum Kılavuzu

Bu kılavuz, **avenoxbeyin v2.1** ikinci beyin sistemini **Google Antigravity** üzerinde çalıştırmak için hazırlanmıştır.

---

## ⚡ Hızlı Başlangıç

### 1. Depoyu Klonlayın

```bash
git clone https://github.com/avenoxai/avenoxbeyin.git
cd avenoxbeyin
```

### 2. Kurulum Betiğini Çalıştırın

```bash
python scripts/install_antigravity.py --vault-path "C:/Users/Kullanici/Documents/BeynimOS" --user-name "Adiniz" --user-bio "Yazilim Gelistirici" --companion "Echo" --os-name "BeynimOS"
```

*(Veya parametresiz çalıştırarak interaktif olarak yanıtlayabilirsiniz: `python scripts/install_antigravity.py`)*

### 3. Kullanmaya Başlayın

1. Oluşturulan vault klasörünü Antigravity ile açın:
   ```bash
   cd "C:/Users/Kullanici/Documents/BeynimOS"
   ```
2. Antigravity oturumunuzu başlatın.
3. Notlarınızı görsel olarak düzenlemek ve grafik görünümünü incelemek için klasörü **Obsidian** uygulamasında (*Open folder as vault*) açın.

---

## ⚙️ Nasıl Çalışır? (Antigravity Entegrasyonu)

Antigravity, proje kökündeki `.agents/` yapılandırmalarını otomatik olarak tanır:

1. **`GEMINI.md` / `AGENTS.md` (Sistem Direktifleri):**
   - AI ortağınızın kişiliğini, klasör düzenini ve hafıza güncelleme protokolünü belirler.
2. **`PreInvocation` Kancası (`.agents/hooks.json`):**
   - Oturum başladığında `🔮 850-Companion/` altındaki hafıza dosyalarını (`Last-Session.md`, `Threads.md`, `Kurallar.md`), derlenmiş bilgi indeksini (`knowledge/index.md`) ve son günlük logları Antigravity bağlamına `ephemeralMessage` olarak otomatik enjekte eder.
3. **`Stop` Kancası (`.agents/hooks.json`):**
   - Oturum tamamlandığında transkripti (`transcript.jsonl`) okur, oturumun Türkçe özetini çıkarır ve `daily/YYYY-MM-DD.md` dosyasına ekler.
4. **Yetenekler (`.agents/skills/`):**
   - **`beyin-doktor`**: Kancaların, logların ve hafıza dosyalarının durumunu tek tabloda doğrular.
   - **`bilgi-derle`**: Günlük logları `knowledge/concepts/` ve `knowledge/index.md` altında birbirine bağlı makalelere derler.
   - **`gecmis-import`**: ChatGPT, Claude veya Google Takeout dışa aktarımlarını vault'a aktarır.

---

## 🤖 Arka Plan Motoru (Özet ve Derleme Öncelik Sırası)

Antigravity üzerinde çalışan `flush.py` (oturum özeti) ve `compile.py` (bilgi derleyici) motorları otomatik olarak şu hiyerarşiyi izler:

1. **Antigravity CLI (`agy -p`):** Açık olan Antigravity oturumunuz üzerinden arka planda sıfır konfigürasyon ve **sıfır API anahtarı** ile çalışır.
2. **Gemini API (`GEMINI_API_KEY`):** İsteğe bağlı olarak Google AI Studio API anahtarı tanımlanmışsa kullanılır.
3. **Claude CLI (`claude -p`):** Sisteminizde Claude CLI yüklüyse kullanılır.
4. **Sıfır Kayıp Yerel Yedek:** Hiçbir araç bulunamazsa oturum diyaloglarını ham formatta `daily/` dosyasına işler, asla veri kaybetmez.

### İsteğe Bağlı API Anahtarı Tanımlama (Opsiyonel)

Eğer harici Gemini API kullanmak isterseniz:
- **Windows (PowerShell):** `[System.Environment]::SetEnvironmentVariable('GEMINI_API_KEY', 'AIzaSy...', 'User')`
- **macOS / Linux:** `export GEMINI_API_KEY="AIzaSy..."`
