# Antigravity ile Avenox Beyin v2.3 kurulumu

Bu dosyayı Google Antigravity içinde, klonlanmış `avenoxbeyin` deposunun kökünde uygula.
Ana kurulum sözleşmesi `SETUP.md` dosyasındadır; onu baştan sona oku ve aynen uygula, yalnızca
aşağıdaki Antigravity farklarını kullan.

## Bağlayıcı farklar

1. Kurulumu Türkçe yürüt ve `SETUP.md` içindeki görüşme, geri alınabilirlik, placeholder ve
   doğrulama kurallarını değiştirme.
2. Önkoşulda `claude` yerine `agy` ara. `python3 -V` ve `agy --version` gerçekten sıfırla
   bitmeden diske yazma. API anahtarı isteme; kullanıcının mevcut Antigravity oturumunu kullan.
3. Yerel Windows'ta Bash yolunu çalıştırma. `SETUP-WINDOWS.md` içindeki yerel Windows akışını
   izle ve kurucuyu `-Harness Antigravity` ile çağır.
4. macOS, Linux veya WSL'de `SETUP.md` MODE A akışını uygula. PHASE 2'de hem
   `render_codex_hooks.py` hem `render_antigravity_hooks.py` çalışmalı.
5. macOS, Linux veya WSL'deki mevcut v1, v2.0, v2.1 veya v2.2 vault için `scripts/upgrade.sh` v2.3
   yükseltmesini kullan. Yerel Windows'ta mevcut vault yükseltmesi hâlâ destek dışıdır; sıfırdan
   `install.ps1 -Harness Antigravity` kurulumu desteklenir.
6. Final raporunda `.agents/hooks.json` içindeki `avenox-beyin` kaydını, mutlak komutları ve
   `.beyin-version = 2.3.0` değerini doğrula.

## Davranış sınırı

Antigravity `PreInvocation` olayı ilk model çağrısında hafıza bağlamını geçici sistem mesajı
olarak ekler. `Stop`, uygulamadan çıkış değil her tamamlanan yürütme döngüsüdür. Bu nedenle adaptör
yalnızca son kullanıcı-asistan alışverişini işler, konuşma başına bir digest tutar ve aynı turu
ikinci kez günlük loga yazmaz. Özet ve derleme mevcut `agy -p` oturumunu kullanır; doğrudan Gemini
API anahtarı veya ikinci bir motor kopyası yoktur.

Kurulumdan sonra Antigravity'yi doğrudan vault kökünde aç. İlk gerçek konuşmadan sonra
`daily/YYYY-MM-DD.md` oluşmasını bekle; oluşmazsa `beyin doktor` çalıştır ve
`.claude/scripts/.state/health.json` dosyasındaki son motor hatasını raporla.
