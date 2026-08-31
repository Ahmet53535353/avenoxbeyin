---
name: bilgi-derle
description: Günlük logları tarar ve knowledge/ altında kavramsal makalelere, bağlantılara ve indekse derler. "bilgi derle", "hafızayı derle", "knowledge compile" dendiğinde kullan.
---

# Bilgi Derleme (Knowledge Compiler)

Bu skill, `daily/` altındaki henüz derlenmemiş günlük oturum loglarını analiz ederek `knowledge/concepts/` altında kavram makalelerine ve `knowledge/index.md` dizinine dönüştürür.

## Kullanım

Kullanıcı bilgi derleme istediğinde terminalde şu komutu çalıştır:

```bash
python .agents/scripts/compile.py
```

İşlem tamamlandığında oluşturulan veya güncellenen kavramları kullanıcıya özetle.
