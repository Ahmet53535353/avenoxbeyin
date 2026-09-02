# Avenox Beyin ile kod ve içerik projeleri

`🏰 300-Projects/` bir proje **hafıza alanıdır**; kod deposu veya medya arşivi değildir. Projenin
amacını, kararlarını, bağlantılarını, mevcut durumunu ve sonraki işini burada tut. Git reposu,
`node_modules`, render çıktıları ve büyük video dosyaları vault dışında kendi klasörlerinde kalsın.

Örnek ayrım:

```text
~/Documents/AylinOS/🏰 300-Projects/youtube-serisi.md   # bağlam ve kararlar
~/Developer/youtube-site/                              # gerçek Git reposu
~/Movies/youtube-serisi/                               # ham medya ve renderlar
```

## Hangi klasörde agent açılmalı?

- Planlama, araştırma, içerik takibi ve uzun dönem hafıza için agent'ı vault kökünde aç.
- Kod değişikliği için agent'ı gerçek Git reposunda aç; o reponun `AGENTS.md`/`CLAUDE.md`
  kuralları ve testleri geçerli olsun.
- İki alanı tek oturumda kullanman gerekiyorsa harness'in ek çalışma alanı özelliğiyle kod reposunu
  vault oturumuna ekle ve kod reposunun kendi talimat dosyasını ayrıca okut. Her iki taraftaki
  dosya sınırını agent'a açıkça söyle.
- İş bittiğinde vault'taki proje notuna yalnız kalıcı sonucu yaz: commit/PR bağlantısı, alınan
  karar, doğrulanan durum ve sıradaki adım. Kaynak kodu vault'a kopyalama.

Bu ayrım sandbox değildir. Avenox Beyin'in derleyicisi model değişikliklerini vault dışında geçici
bir sahnede üretip yalnız `knowledge/` altındaki izinli Markdown dosyalarını geri taşır. Etkileşimli
agent'ın kod reposunda ne okuyup yazabileceğini ise Claude Code, Codex veya Antigravity'nin kendi
izin/sandbox ayarları belirler.

## Video ve diğer içerik projeleri

Video için proje notunda brief, kaynaklar, başlık/thumbnail kararları, yayın durumu ve dosya
konumları tutulabilir. Ham video, ses, proje dosyası ve final render dışarıda kalır. Böylece iCloud
senkronizasyonu ve Obsidian indekslemesi büyük ikili dosyalarla şişmez; beyin yine hangi dosyanın
nerede olduğunu ve hangi kararın alındığını hatırlar.

## OpenCode durumu

v2.2'nin otomatik başlangıç/flush adaptörleri Claude Code, Codex ve Google Antigravity içindir.
OpenCode için resmi bir hook adaptörü şu anda yoktur. OpenCode vault Markdown'ını normal dosya gibi
okuyabilir; fakat bir OpenCode oturumunun kendiliğinden `daily/` loguna yazıldığını veya başlangıçta
hafızayı otomatik aldığını varsayma. Böyle bir destek eklenene kadar OpenCode çıktısının kalıcı
özetini proje notuna elle ya da desteklenen bir harness oturumundan geçirerek kaydet.

## Kısa kural

Vault gerçeğin ve kararların indeksidir; kod reposu uygulamanın kaynağıdır; medya klasörü ağır
dosyaların evidir. Birbirlerine yol ve bağlantıyla referans versinler, fiziksel olarak iç içe
girmesinler.
