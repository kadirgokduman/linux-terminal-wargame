# wargame — Mimari Haritası

> Bu belge `wargame/` deposunun teknik haritasıdır: katmanlar, veri akışı,
> modül sorumlulukları, seviye sözleşmesi, profil matrisi, test değişmezleri ve
> **bağımsız (standalone) CLI** için eksik modül analizi.
>
> İlgili belgeler: [`commands.md`](commands.md) (komut dokümantasyonu),
> [`scenario.md`](scenario.md) (hikâye ve bulmaca dizilimi),
> [`security.md`](security.md) (tehdit modeli), [`deploy.md`](deploy.md) (dağıtım).

---

## 1. Bir bakışta

`wargame`, **bildirimsel bir seviye zincirini** gerçek bir Linux makinesine
materyalize eden bir motordur. İçerik YAML'dir; motor onu dosya sistemine,
kullanıcılara, izinlere, SUID bitlerine, cron işlerine ve yakalanmış ağ
trafiğine dönüştürür. Oyuncu bu makineye SSH ile bağlanır ve gerçek UNIX
araçlarıyla ilerler.

Üç ilke mimariyi belirler:

1. **Mühürler depoda durmaz.** Her parola, HMAC ile bir sırdan ve bir dönem
   etiketinden türetilir (`flags.py`). Depo sızsa bile gelecek mühürler sızmaz.
2. **İçerik bildirimseldir.** Seviye kodu yoktur; `level.yml` vardır. Motor
   yorumlar, `provision.py` uygular, `audit.py` denetler.
3. **Doğrulama zorunludur.** CI, içeriğin kendisiyle çelişmediğini (testler) ve
   seviyenin gerçekten çözülebildiğini (`make validate`) ayrı ayrı kanıtlar.

---

## 2. Katmanlar

```text
        ┌─────────────────────────────────────────────────────────────┐
  İçerik│ levels/NN-slug/level.yml + files/                           │  veri
        └───────────────┬─────────────────────────────────────────────┘
                        │ load_all()
        ┌───────────────▼─────────────────────────────────────────────┐
  Motor │ engine/wargame/  model → flags → provision → audit → stats  │  Python
        │                   (manifest şeması, türetme, materyalizasyon)│
        └───────────────┬─────────────────────────────────────────────┘
                        │ provision (root)
        ┌───────────────▼─────────────────────────────────────────────┐
  Çalışma│ docker/  base.Dockerfile, entrypoint, sshd/PAM, reader.c,  │  OCI imaj
  ortamı │          checker.c, read-only-olmayan kök FS               │
        └───────────────┬─────────────────────────────────────────────┘
                        │ SSH (playerNN)
        ┌───────────────▼─────────────────────────────────────────────┐
  Oyuncu │ gerçek kabuk: grep, find, tar, cron, ss, /proc, sudo, …    │  Linux
        └───────────────┬─────────────────────────────────────────────┘
                        │ PAM open_session
        ┌───────────────▼─────────────────────────────────────────────┐
  Kayıt  │ /var/log/wargame/progress.log → stats.py (skor tablosu)    │
        └─────────────────────────────────────────────────────────────┘
```

| Katman | Dizin | Rol | Dil |
|---|---|---|---|
| İçerik | `levels/` | Seviye tanımları + bulmaca dosyaları | YAML + metin |
| Motor | `engine/wargame/` | Şema, türetme, materyalizasyon, denetim, CLI | Python 3.10+ |
| Çalışma ortamı | `docker/` | İmaj, sshd/PAM, C araçları | Dockerfile, C, sh |
| Dağıtım profili | `deploy/` | Sertleştirilmiş compose + seccomp + nftables | YAML/JSON/nft |
| Araçlar | `scripts/` | Yeni seviye, doğrulama, dönem döndürme | Bash |
| Testler | `tests/` | Şema/bulmaca değişmezleri | pytest |
| İçerik docs | `docs/levels/` | Oyuncuya açık seviye sayfaları (çözümsüz) | Markdown |
| Çözümler | `solutions/` | Referans çözümler — **commit edilmez** | Bash |

---

## 3. Veri akışı: materyalizasyon

Konteyner açılışında tek bir zincir çalışır (`docker/entrypoint.sh`):

```text
entrypoint.sh
  ├─ sır kontrolü (WARGAME_SECRET_FILE)
  ├─ python3 -m wargame provision --quiet
  │     ├─ model.load_all(levels/)          # şema doğrulama + dataclass
  │     ├─ flags.derive_flag(secret, NN, epoch)   # her seviye + final için
  │     ├─ Provisioner.run()
  │     │     ├─ _ensure_base_dirs()        # /etc/wargame/pass, /etc/cron.d
  │     │     ├─ _ensure_users()            # player00..player(N+1), uid 3000+i
  │     │     ├─ _apply_passwords()         # pass/NN (0400) + chpasswd
  │     │     └─ her seviye için _apply_level()
  │     │           ├─ dirs  → _ensure_dir
  │     │           ├─ files → render şablon → (xor?) → (pad_to?) → _write
  │     │           ├─ archives → deterministik tar(.gz/.bz2/.xz)
  │     │           ├─ acls  → setfacl (yalnızca sertleştirilmiş profilde)
  │     │           ├─ pcaps → libpcap çerçeveleri
  │     │           └─ cron  → /etc/cron.d/wargame-NN-i
  ├─ /usr/sbin/cron                         # gerçek zamanlayıcı
  └─ exec /usr/sbin/sshd -D -e
```

Materyalizasyon **idempotenttir**: `_write` içeriği karşılaştırır ve yalnızca
değiştiyse yazar. Arşivler `mtime=0` ve sıralı üyelerle üretilir; aynı girdi
aynı baytları verir (`test_archive_bytes_are_deterministic`).

**Kritik sıra:** `_write` her zaman `chown` → `chmod` sırasını izler ve `chmod`
koşulsuzdur; çünkü `chown`, sahip değişmese bile SUID/SGID bitlerini temizler.

Oturum açma kaydı ayrı bir yol izler:

```text
sshd → PAM (session) → pam_exec → record-login.sh
                                  └─ open_session && player* ise
                                     /var/log/wargame/progress.log'a satır
                                          ↓
                                   python -m wargame stats
```

---

## 4. Modül envanteri

| Modül | Sorumluluk | Anahtarlar |
|---|---|---|
| `model.py` | YAML şeması, doğrulama, `Level`/`FileSpec`/`ArchiveSpec`/`AclSpec`/`PcapSpec`/`CronSpec`, şablon motoru | `load_level`, `load_all`, `render`, `build_context`, `template_variables`, `LevelError` |
| `flags.py` | Mühür türetimi (HMAC-SHA256 + base32), sır yükleme | `derive_flag`, `load_secret`, `SecretError`, `FLAG_LENGTH=20` |
| `provision.py` | Bildirimi dosya sistemine uygular; kullanıcı/parola/izin/arşiv/cron | `Provisioner`, `PASS_DIR`, `UID_BASE=3000` |
| `audit.py` | Sızıntı ve izin denetimi (düz/base64/hex mühür araması, izin karşılaştırma) | `audit`, `AuditReport`, `Finding` |
| `stats.py` | İlerleme defterini okur, skor tablosu üretir | `read_log`, `build_report`, `format_report`, `to_json` |
| `pcap.py` | Bağımlılıksız libpcap üreticisi (Ethernet/IP/TCP elle) | `build_capture` |
| `policy.py` | Profil anahtarları (`no_new_privs` ↔ SUID) | `suid_disabled`, `effective_mode`, `applies` |
| `cli.py` | Alt komutlar | `check`, `list`, `provision`, `audit`, `flag`, `login`, `stats` |

Motorun dışa bağımlılığı yalnızca **PyYAML**'dir (`engine/pyproject.toml`).

---

## 5. Seviye sözleşmesi

`level.yml` bir seviyenin *ne olacağını* tanımlar; nasıl uygulanacağını
`provision.py` bilir.

```yaml
id: "03"                    # klasör adıyla aynı olmalı
slug: "vault-search"        # klasör adının ikinci parçası
title: "Kasa Araması"
concept: ["find", "-size"]  # öğretilen kavramlar
requires: "02"              # yalnızca bir önceki seviye
estimated_minutes: 12
users: []                   # ek kullanıcılar (isteğe bağlı)
dirs: [...]                 # açık izinli dizinler
files: [...]                # template | content | source
archives: [...]             # iç içe tar.* (mühür arşivde)
pcaps: [...]                # libpcap (mühür HTTP başlığında)
acl: [...]                  # POSIX ACL (sertleştirilmiş profilde ayrıcalık)
cron: [...]                 # @reboot / 5 alanlı
expose: [...]               # çalışma anında üretilen meşru dosyalar
flag: { owner: playerNN, mode: "0400" }
hints: [en az 2 kademe]
docs: docs/levels/03.md
```

### Şablon değişkenleri

| Değişken | Değer |
|---|---|
| `{{user}}` | dosyanın sahibi (`player03`) |
| `{{level}}` / `{{slug}}` / `{{title}}` | seviye alanları |
| `{{flag}}` | bu seviyenin ürettiği mühür (`pass/04`) |
| `{{flag:05}}` | açıkça belirtilen mühür |
| `{{flag:05\|b64}}` / `{{flag:05\|hex}}` | kodlanmış hâli |

> **Yapısal kural:** bir seviye yalnızca **bir sonraki** mührü açığa çıkarabilir.
> `{{flag:09}}` yazmak `make check` tarafından reddedilir ve CI'daki
> `test_level_only_exposes_its_own_next_flag` bunu ayrıca kanıtlar.

### Üreticiler (producers)

| Alan | Ne üretir | Oyuncunun gördüğü araç |
|---|---|---|
| `files.content/template/source` | metin, şablon ya da imajdaki ikili | `cat`, `file`, `ltrace` |
| `pad_to` | sabit genişlikli kayıt (`find -size Nc`) | `find` |
| `encoding: xor` | içeriği 0x5A ile gizler | `objdump`, `ltrace`, `gdb` |
| `archives` | deterministik `tar`/`gz`/`bz2`/`xz`, iç içe | `file`, `tar -ztvf/-xzvf` |
| `pcaps` | libpcap dosyası, mühür HTTP'de | `tcpdump -r -A`, `strings` |
| `cron` | `/etc/cron.d/wargame-NN-i` | `ls /etc/cron.d`, `cat` |
| `acl` | `setfacl u:USER:perms` | `getfacl`, `ls -l` (`+`) |

---

## 6. İki profil

Proje aynı içeriği iki farklı ayrıcalık rejiminde oynar. `policy.py` bunu
tek bir ortam değişkeniyle yönetir: `WARGAME_DISABLE_SUID`.

| | `compose.yaml` | `deploy/container-compose.yaml` |
|---|---|---|
| `no-new-privileges` | `false` (SUID gerekli) | `true` |
| SUID/SGID | yazılır | hiç yazılmaz |
| seccomp | Docker varsayılanı | `deploy/seccomp.json` |
| Bellek / CPU / PID | 1g / 1.0 / 512 | 512m / 1.0 / 100 |
| Port | 2222 | 2223 |
| Seviye 02 | SUID okuyucu + `find -perm -4000` | POSIX ACL + `getfacl` |
| Seviye 09 | `sudo -l` + GTFOBins | ayrıcalıklı iş + kullanıcı betiği |
| `wargame audit` | 1 beklenen bulgu (SUID) | 0 bulgu |

`setcap` bu denklemin çözümü değildir: `no_new_privs` dosya yeteneklerini de
yok sayar. NNP ile uyumlu tek ayrıcalık yolu **dosya izni/ACL**'dir
(gerekçe ve ölçüm: `docs/security.md`, `docs/levels/02.md`).

---

## 7. Test mimarisi

İki ayrı doğrulama katmanı vardır ve **farklı soruları** yanıtlarlar:

**A. Şema ve bulmaca değişmezleri** (`tests/`, çözüm gerektirmez):
- zincir bütünlüğü: id'ler kesintisiz, `requires` bir önceki;
- mühür izolasyonu: bir seviye yalnızca kendi sonraki mührünü taşır;
- `flag` her zaman `0400` ve oyuncuya ait;
- ev dosyaları seviye kullanıcısına ait (SUID istisnası hariç);
- bulmaca mekaniği: 03 sabit genişlik, 04 tek `sealed` satır, 06 iç içe arşiv,
  07 yalnızca loopback, 08 ortamda mühür, 09 dar sudo + NNP yedeği,
  10 pcap mührü, 11 XOR;
- geçersiz tanımlar reddedilir: id/klasör uyuşmazlığı, `requires` atlama,
  yol kaçışı (`..`), bilinmeyen şablon değişkeni/filtre.

**B. Uçtan uca çözülebilirlik** (`scripts/validate-level.sh`, çözüm gerektirir):
izole bir compose projesi kurar, `playerNN` olarak `solutions/NN.sh` çalıştırır,
son satırı beklenen mühürle karşılaştırır, sonra `wargame audit` koşar.

Çözümler halka açık repoda tutulmadığından (B) varsayılan olarak atlanır;
bakımcılar `make validate` ile kendi ortamlarında koşar. Bu, "seviye gerçekten
çözülebilir" iddiasını doğrulanabilir kılar.

---

## 8. Genişleme noktaları

| İstek | Yapılacak | Değmez mi? |
|---|---|---|
| Yeni seviye | `make new-level ID=NN TITLE="…"` + `level.yml` doldur | — |
| Yeni ayrıcalık profili | `policy.py`'ye `when` değeri + `apply` beklemesi | nadiren gerekir |
| Yeni üretici (ör. SQLite, systemd unit) | `model.py`'de spec + `provision.py`'de `_apply_*` | yalnızca gerçek bir ders veriyorsa |
| Yeni denetim kontrolü | `audit.py`'ye `Finding` + `_check_*` | artan sızıntı yüzeyi varsa |
| Yeni dağıtım hedefi | `deploy/`'e compose profili | — |

---

## 9. Bağımsız (standalone) CLI analizi

**Mevcut gerçek.** `wargame`, Docker + root + gerçek sshd/cron + gerçek UNIX
kimlikleri olmadan **çalışmaz**. Motor bilerek "kurulum" katmanıdır; oynanış
gerçek makinede olur. Yani bugünkü "bağımsız" tanımı: *tek bir depo, tek bir
`make up`, tarayıcı gerekmez* — ama Docker gerekir.

Aşağıdaki tablo, **bağımlılıksız (Docker'sız) bir yerel CLI oynanışı** için
eksik parçaları listeler. Hiçbiri bugün yoktur.

| # | Eksik modül | Neden gerekli | Zorluk |
|---|---|---|---|
| 1 | **Sanal kabuk / komut yorumlayıcı** | Şu an komutları gerçek `/bin/sh` çalıştırır; CLI'da bir yorumlayıcı gerekir | Yüksek |
| 2 | **VFS katmanı** | Seviyeler gerçek mutlak yollara yazar (`/home`, `/srv`, `/etc`); CLI'da sandbox dizini + overlay gerekir | Orta–Yüksek |
| 3 | **Sanal kimlik modeli** | `playerNN` gerçek UID/`/etc/passwd`'e bağlıdır; CLI'da sanal kullanıcı/kişi gerekir | Orta |
| 4 | **İlerleme/cevap akışı** | İlerleme bugün "sonraki kullanıcıyla SSH"; CLI'da `submit` + kayıt dosyası gerekir | Düşük–Orta |
| 5 | **Ayrıcalık ilkelleri** | SUID, `sudo`, ACL, `cron`, `/proc/<pid>/environ`, loopback servisi işletim sistemi seviyesindedir; taşınabilir simülasyonu zordur | Yüksek |
| 6 | **Kayıt/yükleme (save)** | `stats.py` sunucu günlüğünü okur; oyuncu tarafı kayıt yoktur | Düşük |
| 7 | **Sorulabilir ipuçları** | `hints` yalnızca YAML'de durur; oyun içi `hint` komutu yoktur | Düşük |
| 8 | **Seviye başına `answer`/`check`** | Şema dosya sistemini tanımlar, çözüm kontrolünü değil | Düşük–Orta |
| 9 | **Paketleme/dağıtım** | Konsol betiği var ama PyPI/single-file yayın yok | Düşük |
| 10 | **Etkileşimli eğitim** | `pwd`/`ls`'i öğreten ayrı bir "tur" modu yok | Düşük |

### Seçenekler

| Seçenek | Ne yapar | Sonuç |
|---|---|---|
| **A. Docker kalır, CLI ince bir kabuk olur** | `wargame play --local`, seviyeleri geçici bir dizine materyalize eder; gömülü komut seti (`ls`,`cat`,`grep`,`find`,`base64`,`tar`,`strings`) ile VFS üzerinde oynanır. OS ilkelleri (SUID/sudo/proc) bu modda **kısaltılır** ve işaretlenir. | Haftalar; içerik aynı kalır, iki mod olur |
| **B. Tam simülasyon motoru** | Gerçek `/bin/sh` yerine kendi kabuk + tam VFS + sanal izin modeli. | Aylar; ancak **Sigillatus çekirdeğiyle ortak** hale gelir |
| **C. Yayın için dokunma** *(seçildi)* | Docker-only kalır; README, dokümanlar ve etiketler tamamlanır. | Günler; en hızlı GitHub yayını |

### Karar — Seçenek C (2026-10-28)

**Docker Compose + SSH kanonik çalışma ortamı olarak kalır.** Motor
(`engine/wargame/`) ve katman yapısı (`levels/`, `docker/`, `deploy/`,
`scripts/`, `tests/`) olduğu gibi korunur; sanal kabuk, VFS ya da sanal
kimlik modeli yazılmaz. Gerekçe:

1. **Dersin kendisi işletim sistemidir.** SUID, `sudo`, ACL, `cron`,
   `/proc/<pid>/environ` ve loopback servisi çekirdek seviyesinde yaşar;
   bunları taklit eden bir CLI, oyunun öğrettiği şeyi değiştirir
   (yukarıdaki 10 eksik modülün 5'i tam olarak bu yüzden "yüksek" zorluktadır).
2. **Taşınabilir çalışma zamanı `Sigillatus`'un işi.** Aynı simülasyon
   çekirdeğini burada yeniden yazmak, iki kod tabanını erkenden ayırır ve
   mühür şemasının tek kaynaktan yönetilmesini zorlaştırır
   ([`strategy.md`](strategy.md) §5 riskler tablosu).
3. **Eksik olan simülasyon değil, yayın.** Depo bugün `make up` ile
   çalışıyor; yayın önündeki engeller dokümantasyon, etiketler ve lisans
   başlığıdır.

Sonuç olarak `wargame`, gerçek işletim sisteminin **içerik laboratuvarı**
olarak konumlanır. A ve B iptal edilmedi, **ertelendi**: yerel (Docker'sız)
oynanış gerçek bir oyuncu talebine dönüşürse A yeniden değerlendirilir;
ortak çekirdek kararı `strategy.md` §6 Faz 4'te bekler.

---

## 10. Bilinen sınırlar

- **Konteyner kaçışı** teorik olarak mümkündür; anonim kullanıcı kabul eden
  bir servis için gVisor/Firecracker önerilir (`docs/security.md`).
- **Kök dosya sistemi yazılabilir** (PAM `/etc/shadow`'a yazar); telafi
  tek kullanımlık imajdır.
- **SUID ↔ NNP** aynı anda kullanılamaz; iki profil bu yüzden farklı mekanizma
  öğretir. Bu bilinçli bir ödündür, hata değildir.
- **Tek konteyner** tüm oyuncuları barındırır; izolasyon konteyner sınırındadır,
  oyuncular arasında tam değildir.
- **Lisans seçilmemiştir** (`LICENSE` yok). Karar bilinçli olarak yayın
  sonrasına bırakıldı; ayrıntı [`strategy.md`](strategy.md) §7.
