---
name: gecmis-import
description: Eski sohbet geçmişini (ChatGPT, Claude, Gemini Takeout dışa aktarımları) vault'un günlük log formatına çevirip derleyicinin sindirmesi için daily/ altına yazar. "geçmiş import", "geçmişimi aktar", "takeout", "chatgpt geçmişi", "eski sohbetlerimi beyne yükle" dendiğinde kullan.
---

# Geçmiş İçe Aktarımı (Google Antigravity)

Eski sohbet arşivini beynin normal hattına sokar. Dışa aktarım dosyası yerelde okunur,
sohbetler aylara bölünür ve `daily/import-YYYY-MM-part-NNN.md` dosyalarına yazılır.
Akşam derleyicisi bu dosyaların içeriğini normal günlük loglar gibi okur ve bilgi tabanına aktarır.

## Zorunlu Onay Kapısı

Agent aşağıdaki adımları sırayla tamamlamak ZORUNDADIR. Kullanıcının izni olmadan dışa aktarım
dosyasını açmak, ayrıştırmak veya `daily/` altına dosya yazmak YASAKTIR.

1. Agent veri akışını açıkça anlatır: dışa aktarım yerelde okunur, seçilen sohbetler
   yerel `daily/` dosyalarına yazılır, derleyici bu dosyaların içeriğini özetler. Bunun dışında hiçbir yere
   yükleme veya gönderim yapılmaz.
2. Agent özel ve hassas sohbetlerin varsayılan olarak dahil olacağını söyler.
   Kullanıcıya başlangıç ve bitiş tarihi sınırı ile hariç tutma kelimeleri sunar.
3. Kullanıcıdan onay alındıktan sonra işlem başlatılır.
