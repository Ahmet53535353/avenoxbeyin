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

## 🔑 İsteğe Bağlı: Gemini API Anahtarı

Oturum kapandığında arka planda otomatik özet çıkarma ve bilgi derleme için ortam değişkeni olarak `GEMINI_API_KEY` tanımlayabilirsiniz:

- **Windows (PowerShell):**
  ```powershell
  [System.Environment]::SetEnvironmentVariable('GEMINI_API_KEY', 'AIzaSy...', 'User')
  ```
- **macOS / Linux (Bash/Zsh):**
  ```bash
  export GEMINI_API_KEY="AIzaSy..."
  ```

*(API anahtarı bulunamazsa sistem yüklü olan `claude` CLI varsa onu kullanır veya bildirim üretir).*
