# Güvenlik Modeli

Bu proje, anonim kullanıcılara **kasıtlı olarak zayıf** bir Linux makinesi
sunar. Tehdit modeli bu gerçeği kabul ederek kurulur.

## Varlıklar

| Varlık | Önemi |
|---|---|
| Ana sunucu (host) | Kritik — konteyner kaçışı buraya çıkar |
| Gelecek seviyelerin mühürleri | Yüksek — oyunun bütünlüğü |
| Oyuncu verisi (IP, giriş kaydı) | Orta — KVKK/GDPR |
| Sunucu kaynakları | Orta — kripto madenciliği, DDoS |

## Tehditler ve karşılıklar

| Tehdit | Karşılık | Durum |
|---|---|---|
| Konteynerden kaçış | cap_drop, `deploy/seccomp.json`, tek kullanımlık imaj; ileri seviye: gVisor / Firecracker | Kısmi |
| İleri seviye mühür okuma | `0400` + seviye başına kullanıcı + `make audit` sızıntı testi | Var |
| Mühür sızması (GitHub/Discord) | HMAC türetme + dönem rotasyonu; depoda hiç flag yok | Var |
| Fork bombası / kaynak tükenmesi | `pids_limit`, `ulimits nproc`, `pam_limits` | Var |
| Bellek/CPU tükenmesi | `mem_limit`, `cpus`, `--memory-swap` | Var |
| Dışarı sızma / madencilik | Host firewall ile konteyner çıkışının kapatılması | **Yapılmalı** |
| SSH kaba kuvvet | `MaxAuthTries 3`, `MaxStartups`, fail2ban/CrowdSec | Kısmi |
| Oyuncular arası saldırı | Ayrı UID'ler; `AllowUsers player*` | Kısmi |
| Kalıcılık (anahtar, tünel) | `PubkeyAuthentication no`, forwarding kapalı | Var |

## Sertleştirilmiş profil

`deploy/container-compose.yaml` şunları açar:

- `no-new-privileges: true`
- `deploy/seccomp.json`: `mount`, `unshare`, `setns`, `bpf`, `kexec_load`,
  `reboot`, `swapon`, modül yükleme ve kernel anahtarlığı engellenir
- `mem_limit 512m`, `cpus 1.0`, `pids_limit 100`

`WARGAME_DISABLE_SUID=1` ile gelir: materyalizasyon SUID/SGID bitlerini
hiç yazmaz, denetim de onları beklemez. SUID'ye dayanan iki seviye
NNP uyumlu yedek mekanizmaya geçer:

| Seviye | Oynanabilir profil | Sertleştirilmiş profil |
|---|---|---|
| 02 — Mühür Okuyucusu | SUID okuyucu + `find -perm -4000` | POSIX ACL: `/etc/wargame/pass/03` üzerinde `u:player02:r` → `getfacl` ile keşif |
| 09 — Dar Kapsam | `sudo -l` + GTFOBins (`find -exec`) | Kullanıcının yazabildiği betiği `player10` adına çalıştıran ayrıcalıklı iş (`delegate-10`) |

Sonuç: `bash scripts/validate-all.sh` iki profilde de **12/12 PASS**.
Ödün: sertleştirilmiş profilde SUID dersi kaybolur, yerine ACL/iş
tasarımı dersi geçer.

**Neden `setcap` değil?** `no_new_privs` yalnızca setuid bitini değil,
dosya yeteneklerini de etkisiz kılar. Ölçüm: `setcap
cap_dac_read_search+ep` verilmiş bir biner NNP'siz mühürü okudu, aynı
biner `no-new-privileges:true` altında `Permission denied` verdi. Yani
NNP ile uyumlu tek ayrıcalık yolu dosya izni/ACL'dir.

## Üretim öncesi zorunlu adımlar

1. **Çıkışı kapat.** Konteyner ağının dışarı çıkmasını engelle; yalnızca
   yayınlanan SSH portuna giriş kalsın.

   ```nft
   table inet wargame {
     chain forward {
       type filter hook forward priority filter; policy accept;
       ip saddr 172.28.0.0/16 ip daddr 172.28.0.0/16 accept
       ip saddr 172.28.0.0/16 drop
       ct state established,related accept
     }
   }
   ```

   Aralık `WARGAME_SUBNET` ile değiştirilebilir (varsayılan `172.28.0.0/16`).
   Kuralı yazdıktan sonra `nft list ruleset` ile doğrulayın.

2. **Sırrı Docker secret yap.** `WARGAME_SECRET` dosyası imaja girmez;
   `make secret` yalnızca yerel geliştirme içindir. Üretimde 32 baytlık
   rastgele bir sır ve ayrı bir dönem etiketi kullanın.

3. **Log saklama süresi koy.** `/var/log/wargame/progress.log` kişisel veri
   içerir; 30 gün sonra silin.

4. **Tek kullanımlık düğüm.** Konteyner her deploy'da sıfırdan kurulur;
   `docker commit` ile alınan anlık görüntüler üretimde kullanılmaz.

5. **Skor tablosunu ayır.** PAM kaydı yalnızca yerel dosyaya yazar; dışa
   açık bir API'ye gönderiyorsanız HMAC imzası kullanın.

## Bilinen sınırlar

- **Konteyner kaçışı** bu kurulumda teorik olarak mümkündür. Anonim
  kullanıcı kabul eden bir servis için gVisor (`runsc`) veya Firecracker
  microVM önerilir; SUID ve `/proc` semantiği farklı olacağı için
  seviyeler yeniden test edilmelidir.
- **SUID + `no-new-privileges`** aynı anda kullanılamaz. Oynanabilir
  profilde SUID dersi için NNP kapalıdır; bunun bedeli, imaj içindeki
  herhangi bir SUID yanlış yapılandırmasının gerçek yetki yükseltmesine
  dönüşebilmesidir. `make audit` bunu yakalar (beklenen tek bulgu:
  seviye 02 okuyucusu). Sertleştirilmiş profilde NNP açıktır ve SUID
  hiç yazılmaz; orada SUID dersi ACL/iş dersine dönüşür.
- **Dosya sistemi yazılabilir.** PAM `/etc/shadow` üzerine yazar. Salt
  okunur kök dosya sistemi parola zincirini kırar.
