---
name: beyin-doktor
description: Antigravity için beynin sağlık kontrolü. Kancalar, scriptler, hafıza dosyaları, günlük loglar ve derleme durumunu tek tabloda denetler. "beyin doktor", "doktor", "sağlık kontrolü", "beyin çalışıyor mu" dendiğinde kullan.
---

# Beyin Doktoru (Google Antigravity)

Bu yetenek (skill) beynin mekanik katmanını denetler: Antigravity kancaları bağlı mı, Python scriptleri erişilebilir mi, loglar ve hafıza güncel mi.

## Nasıl Çalışır

1. Vault kökünde çalışır (`GEMINI.md` dosyasının bulunduğu dizin).
2. Aşağıdaki kontrolleri Python veya Bash ile sırayla çalıştırır.
3. Her kontrolün çıktısını 🟢 / 🟡 / 🔴 olarak sınıflandırır.
4. Sonucu tek bir özet tabloda verir.

## Kontroller

### 1. Antigravity Kancaları (`.agents/hooks.json`)
- `.agents/hooks.json` dosyası mevcut mu?
- `PreInvocation` ve `Stop` olayları tanımlı mı?

### 2. Script Dosyaları
- `.agents/scripts/pre_invocation.py` var mı?
- `.agents/scripts/stop.py` var mı?
- `.agents/scripts/flush.py` var mı?
- `.agents/scripts/compile.py` var mı?

### 3. Hafıza Katmanı (`🔮 850-Companion/`)
- `Core.md`, `Kurallar.md`, `Last-Session.md`, `Threads.md`, `Journal.md` mevcut mu?

### 4. Bilgi ve Günlük Katmanı
- `daily/` klasörü ve bugünün logu var mı?
- `knowledge/index.md` mevcut mu?

### 5. LLM API Anahtarı
- Ortamda `GEMINI_API_KEY` veya `GOOGLE_API_KEY` tanımlı mı?
