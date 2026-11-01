# wargame — terminal tabanlı CTF / wargame

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-Docker-informational)
![Levels](https://img.shields.io/badge/levels-12-success)
![License](https://img.shields.io/badge/license-MIT-green)

> **English.** `wargame` is a self-contained CTF-style level ladder that runs on
> a real Linux machine over SSH. Flags are never stored in the repo — they are
> derived with HMAC from a server secret and an epoch, so the repository can be
> public without leaking future passwords. Every level is declarative YAML and
> CI proves the content is solvable. Docs are written in Turkish.

Gerçek bir Linux makinesine SSH ile bağlanıp dosya izinleri, süreçler,
zamanlanmış işler, yerel servisler ve ayrıcalıklar üzerinden ilerlediğiniz
12 seviyelik bir zincir. Grafik yok, tarayıcı yok: yalnızca kabuk.

OverTheWire Bandit'in öğretme modelini (her seviye bir UNIX kullanıcısı, her
bulmaca bir sonrakinin parolası) alır; üzerine iki şey ekler:

1. **Mühürler depoda durmaz.** Her parola, sunucudaki bir sırdan ve bir dönem
   etiketinden HMAC ile türetilir. Depo sızsa bile gelecekteki mühürler
   sızmaz; dönem değişince eski parolalar ölür.
2. **Her seviye test edilebilir.** Seviye tanımı bildirimsel bir YAML
   dosyasıdır; CI içeriğin kendisiyle çelişmediğini, bakımcılar da seviyenin
   gerçekten çözülebildiğini kanıtlar.

> **Durum:** 12 seviye (`00`–`11`), CI hattı ve sertleştirilmiş dağıtım profili.
> Lisans henüz seçilmedi (bkz. [Lisans](#lisans)).

---

## Hızlı başlangıç

Gereksinimler: **Docker** + **Docker Compose v2**.

```bash
make up          # imajı kurar, sandbox'ı başlatır, player00 parolasını yazar
ssh player00@localhost -p 2222
```

Parolayı tekrar görmek için:

```bash
make bootstrap   # ssh satırı + player00 parolası
```

İlk üç komut:

```bash
pwd
ls -la
cat welcome.txt   # mühür 01 burada
```

---

## Oyun modeli

```text
player00 ──(mühür 01)──▶ player01 ──(mühür 02)──▶ player02 ──(mühür 03)──▶ ... ──▶ mühür 12
```

- `playerNN` kullanıcısı, kendi ev dizinindeki bulmacayı çözer.
- Bulmaca, `playerNN+1` kullanıcısının parolasını verir.
- Parolalar `/etc/wargame/pass/NN` altında `0400` izinle durur.
- Bütün seviyeler tek konteynerde yaşar; izolasyon konteyner sınırındadır.
- İlerleme, PAM üzerinden `/var/log/wargame/progress.log` dosyasına yazılır
  (`make stats` bunu özetler).

---

## Seviyeler

| ID | Başlık | Kavram | ~dk |
|---|---|---|---|
| 00 | Eşik | `pwd`, `ls -la`, `cat`, izinler | 3 |
| 01 | Defter | `grep -r`, `base64 -d` | 8 |
| 02 | Mühür Okuyucusu | SUID, `find -perm -4000` (yedek: ACL) | 12 |
| 03 | Kasa Araması | `find -size`, `-user`, sabit genişlikli kayıtlar | 12 |
| 04 | Kayıt Okuma | `grep -E`, `awk`, yapılandırılmış log | 10 |
| 05 | Kendiliğinden | `cron`, `/etc/cron.d`, `@reboot`, çıktı yakalama | 12 |
| 06 | Katmanlar | `file`, `tar -ztvf/-xzvf`, bzip2, iç içe arşiv | 15 |
| 07 | Kapalı Kapı | `ss -tulpn`, `curl`, yalnızca loopback'te dinleyen servis | 12 |
| 08 | Görünmez Yolcu | `ps aux`, `/proc/<pid>/environ`, `strings` | 12 |
| 09 | Dar Kapsam | `sudo -l`, `sudo -u`, GTFOBins (`find -exec`) | 15 |
| 10 | Kayıt Altında | `tcpdump -r`, `-A`, pcap, HTTP başlıkları | 12 |
| 11 | Kuşatılmış Sır | `file`, `objdump`, `ltrace`, `gdb`, XOR | 20 |

Oyuncuya açık seviye sayfaları: [`docs/levels/`](docs/levels/) (çözümsüz).
Tam hikâye akışı ve bulmaca dizilimi: [`docs/scenario.md`](docs/scenario.md).

Zincirin kapanışı ayrı bir seviye tanımı değildir: mühür 12 son kimliğe
(`player12`) götürür ve oyun [`docs/levels/12.md`](docs/levels/12.md)
sayfasındaki kapanış metniyle biter.

---

## Hikâye

Oyuncu, kapanmakta olan bir arşivin terminaline **custodian** kimliğiyle
bağlanır. Kimliği bir isim değil bir görevdir; arşiv, açılmış mühürlerin
sayısıyla ayakta kalır. Her seviye bir UNIX kullanıcısı, her mühür bir sonraki
kapının anahtarıdır.

```text
  ┌──────────────────────────────────────────────────────────────┐
  │  C A L D E R   R E A C H   ·   A R Ş İ V   T E R M İ N A L İ  │
  └──────────────────────────────────────────────────────────────┘
  Hoş geldin, custodian.
  Bu makinede iki şey var: kapanmakta olan bir arşiv ve onu
  kapatmaya çalışan bir sayaç. Mühürler açıldıkça arşiv nefes alır.
```

---

## Depo haritası

```text
levels/NN-slug/    seviye tanımı (level.yml) + bulmaca dosyaları
engine/wargame/    mühür türetme, materyalizasyon, denetim, pcap, CLI
docker/            base imajı, sshd/PAM yapılandırması, entrypoint, C araçları
deploy/            sertleştirilmiş profil (seccomp, kaynak limitleri, nftables)
scripts/           yeni seviye, doğrulama, dönem değiştirme
tests/             birim testleri + bulmaca değişmezleri
docs/levels/       oyuncuya açık seviye sayfaları (çözümsüz)
solutions/         referans çözümler — commit edilmez
```

---

## Dokümantasyon

| Belge | İçerik |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Mimari haritası, veri akışı, modül envanteri, seviye sözleşmesi, test değişmezleri, **bağımsız CLI analizi (Seçenek C kararı)** |
| [`docs/levels/12.md`](docs/levels/12.md) | Seviye 12 — kapanış: son mühür, final mesajın kanonik metni, çözümsüz |
| [`docs/commands.md`](docs/commands.md) | Motor CLI referansı, `make` hedefleri, ortam değişkenleri, oyun içi komut aileleri, çıkış kodları |
| [`docs/scenario.md`](docs/scenario.md) | Tam hikâye akışı, perde yapısı, 12 seviyenin bulmaca dizilimi |
| [`docs/strategy.md`](docs/strategy.md) | Bu proje ile Unity tabanlı ana oyun arasındaki karşılaştırma ve yol haritası |
| [`docs/security.md`](docs/security.md) | Tehdit modeli ve üretim öncesi zorunlu adımlar |
| [`docs/deploy.md`](docs/deploy.md) | Dağıtım profilleri ve işletim |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Yeni seviye sözleşmesi ve inceleme süreci |

---

## Nasıl çalışır

1. `docker/entrypoint.sh`, konteynerde `python3 -m wargame provision` çalıştırır.
2. Motor, `levels/*/level.yml` dosyalarını okur; her seviye için
   `/home/playerNN` altındaki dosyaları şablonlardan üretir, sahiplik ve
   izinleri uygular, `/etc/wargame/pass/NN` mühürlerini yazar.
3. Aynı anda her oyuncunun parolası `chpasswd` ile o mühre eşitlenir.
4. `sshd` açılır; her giriş PAM üzerinden `/var/log/wargame/progress.log`
   dosyasına yazılır (skor tablosu için tek gerçek kaynak).

Materyalizasyon **idempotenttir**: `make restart` aynı durumu yeniden üretir.
Ayrıntılı veri akışı: [`docs/architecture.md`](docs/architecture.md) §3.

---

## Güvenlik modeli

Bu proje **kasıtlı olarak** zayıf yapılandırılmış bir makine sunar. Gerçek bir
sunucuda çalıştırmadan önce [`docs/security.md`](docs/security.md) okunmalıdır.
Özet:

- Konteyner: `cap_drop: ALL` + yalnızca gereken 6 capability, `pids_limit`,
  `mem_limit`, `cpus`, `ulimits`, tmpfs `/tmp` ve `/run`.
- Dış ağ kapatılmalıdır (host firewall / `DOCKER-USER` zinciri).
- `no-new-privileges` bilinçli olarak kapalı: SUID seviyeleri aksini imkânsız
  kılar. İzolasyon konteyner sınırında sağlanır.
- Kök dosya sistemi yazılabilir: PAM `/etc/shadow` üzerine yazmak zorundadır.
  Telafi: tek kullanımlık imaj.
- Mühürler 100 bit entropi taşır; tahmin edilemez.

---

## İki profil

Oynanabilir profil `compose.yaml`'dır. Üretim için daha sıkı bir profil var:

```bash
docker compose -f deploy/container-compose.yaml up -d
```

| | `compose.yaml` | `deploy/container-compose.yaml` |
|---|---|---|
| Bellek / CPU / PID | 1g / 1.0 / 512 | 512m / 1.0 / 100 |
| seccomp | Docker varsayılanı | `deploy/seccomp.json` |
| `no-new-privileges` | false (SUID gerekli) | true |
| Port | 2222 | 2223 |
| Seviye 02 | SUID okuyucu + `find -perm -4000` | POSIX ACL + `getfacl` |
| Seviye 09 | `sudo -l` + GTFOBins | ayrıcalıklı iş + kullanıcı betiği |
| `wargame audit` | 1 beklenen bulgu (SUID) | 0 bulgu |

`no-new-privileges` SUID'i tanımı gereği engeller; bu yüzden sertleştirilmiş
profil `WARGAME_DISABLE_SUID=1` ile gelir ve SUID'ye dayanan iki seviye NNP
uyumlu yedek mekanizmalara geçer. Sonuç: **her iki profilde de 12/12 PASS.**

`setcap` bu çelişkiyi çözmez: `no_new_privs` altında dosya yetenekleri de yok
sayılır. NNP ile uyumlu tek ayrıcalık mekanizması dosya izni/ACL'dir; ayrıntı
[`docs/security.md`](docs/security.md).

---

## Geliştirici komutları

```bash
make check                    # tüm seviye tanımlarını doğrula
make test                     # birim testleri
make new-level ID=12 TITLE="Başlık"
make validate LEVEL=01        # seviyeyi gerçekten çöz (çözüm varsa)
make validate-all
make validate-hardened        # sertleştirilmiş profilde çöz
make audit                    # çalışan sandbox'ta sızıntı denetimi
make stats                    # skor tablosu: seviye, oturum, süre
make rotate EPOCH=2027Q1      # tüm mühürleri yenile
```

Tam referans (alt komutlar, çıkış kodları, ortam değişkenleri):
[`docs/commands.md`](docs/commands.md).

---

## CI

| İş | Ne yapar |
|---|---|
| `lint` | kabuk sözdizimi (CRLF dahil), `wargame check` |
| `test` | `pytest tests/` — mühür, şablon ve bulmaca değişmezleri |
| `hardening` | `hadolint` (Dockerfile) + `gitleaks` (sır taraması) |
| `build` | imajı derler |
| `solve` | çözümler varsa 12 seviyeyi uçtan uca çözer (varsayılan kapalı) |

---

## Katkı

Yeni seviye eklemek için [`CONTRIBUTING.md`](CONTRIBUTING.md) ve
`make new-level`. Özet kural: bir seviye **tek kavram** öğretir, **önce soru**
sorar, **deterministik** olur, **dış ağa çıkmaz** ve çözümü depoda tutmaz.

Çözümler halka açık repoda tutulmaz; bu yüzden bir seviyenin "çözülebilir"
olduğunu kanıtlayan test betiği de repoda değildir — bakımcılar bunu
`make validate` ile kendi ortamlarında koşar.

---

## Lisans

**MIT.** Ayrıntılar için [`LICENSE`](LICENSE) dosyasına bakın.
