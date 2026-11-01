# wargame — Komut Dokümantasyonu

> İki ayrı komut yüzeyi vardır ve karıştırılmamalıdır:
>
> | Yüzey | Kim kullanır | Nerede çalışır |
> |---|---|---|
> | **Motor CLI** (`python -m wargame …`, `make …`) | bakımcı | geliştirici makinesi |
> | **Oyun içi kabuk** (`grep`, `find`, `tar`, …) | oyuncu | sandbox konteyneri |
>
> İlgili belgeler: [`architecture.md`](architecture.md),
> [`scenario.md`](scenario.md), [`../CONTRIBUTING.md`](../CONTRIBUTING.md).

---

## 1. Motor CLI (bakımcı)

Genel biçim:

```text
python -m wargame [--levels DIR] [--epoch ETIKET] [--secret BASE64] <komut> [seçenekler]
```

| Global seçenek | Varsayılan | Anlam |
|---|---|---|
| `--levels` | `levels` (`WARGAME_LEVELS`) | seviye klasörü |
| `--epoch` | `dev` (`WARGAME_EPOCH`) | mühür dönemi; değiştirmek tüm parolaları geçersiz kılar |
| `--secret` | env/dosyadan | base64 sır (öncelik: argüman > `WARGAME_SECRET` > `WARGAME_SECRET_FILE` > `/run/secrets/wargame_secret`) |
| `--version` | — | sürüm |

### `check` — seviye tanımlarını doğrula

```bash
python -m wargame check
```

Her seviye için kimlik, başlık, dosya sayısı, hedef ve slug yazar; sonunda
toplam seviye sayısını bildirir. Şema ihlallerinde (`LevelError`) çıkış kodu `2`.

### `list` — seviye tablosu

```bash
python -m wargame list
```

```text
ID  BAŞLIK                      KAVRAM                            DK
00  Eşik                        pwd, ls -la, cat, dosya izinleri    3
01  Defter                      grep, base64, dizin gezinme         8
...
```

### `provision` — tanımları dosya sistemine uygula

```bash
python -m wargame provision            # root gerekir, idempotent
python -m wargame provision --dry-run  # ne yapılacağını göster, dokunma
python -m wargame provision --quiet    # özet satırını basma
```

`--dry-run`, `pwd`/`grp` olmayan makinelerde (ör. Windows geliştirme) güvenle
çalışır. Root olmayan gerçek çalıştırma `ProvisionError` ile reddedilir.

### `audit` — sızıntı ve izin denetimi

```bash
python -m wargame audit
python -m wargame audit --quiet   # yalnızca bulguları bas
```

Mühürleri üç kodlamada (düz, base64, hex) `/etc`, `/home`, `/opt`, `/srv`,
`/usr/local`, `/var` kökleri altında arar; tanımlı dosyaların mod/sahiplik ve `flag` dosyasının iznini
karşılaştırır. **Çıkış kodu:** bulgu yoksa `0`, `error` seviyesinde bulgu varsa `1`.
SUID bulgusu `warn` seviyesindedir (oynanabilir profilde beklenir).

### `flag` — mühür değeri

```bash
python -m wargame flag 03          # seviye 03'ün kendi mührü
python -m wargame flag 03 --next   # 04'ün mührü (bir sonraki kapı)
```

### `login` — giriş bilgisi

```bash
python -m wargame login 03
```

```text
ssh player03@localhost -p 2222
parola: <20 karakter base32>
```

`make bootstrap` ve `make up` sonunda (giriş bilgisini basmak için) bu komut kullanılır.

### `stats` — skor tablosu

```bash
python -m wargame stats
python -m wargame stats --json
python -m wargame stats --log /var/log/wargame/progress.log
```

Giriş kaydını okur; seviye başına oturum, ilk/son giriş ve aralık verir;
zincirde hiç açılmamış ilk seviyeyi uyarı olarak bildirir.

---

## 2. `make` hedefleri

| Hedef | Ne yapar | Örnek |
|---|---|---|
| `make help` | hedef listesi | `make help` |
| `make secret` | yerel sır üretir (varsa dokunmaz) | `make secret` |
| `make deps` | `pip install -e ./engine pytest` | `make deps` |
| `make build` | imajı derler | `make build` |
| `make up` | sandbox'ı başlatır + `player00` parolasını basar | `make up` |
| `make down` | durdurur, hacimleri siler | `make down` |
| `make restart` | `down` + `up` | `make restart` |
| `make logs` | konteyner günlükleri | `make logs` |
| `make ps` | durum | `make ps` |
| `make shell` | konteynerde kabuk (`PLAYER=player02`) | `make shell PLAYER=player02` |
| `make bootstrap` | `player00` giriş bilgisi | `make bootstrap` |
| `make test` | `pytest tests -q` | `make test` |
| `make check` | `python -m wargame check` | `make check` |
| `make audit` | çalışan sandbox'ta denetim | `make audit` |
| `make stats` | skor tablosu | `make stats` |
| `make validate` | tek seviyeyi çöz (`LEVEL=01`) | `make validate LEVEL=01` |
| `make validate-all` | tüm seviyeleri çöz | `make validate-all` |
| `make validate-hardened` | sertleştirilmiş profilde çöz | `make validate-hardened` |
| `make new-level` | yeni seviye iskeleti | `make new-level ID=12 TITLE="…"` |
| `make rotate` | yalnızca dönemi değiştir | `make rotate EPOCH=2027Q1` |
| `make rotate-epoch` | yeni sır + yeni dönem + temiz konteyner | `make rotate-epoch EPOCH=2027Q1` |
| `make clean` | imajı ve hacimleri sil | `make clean` |

---

## 3. Ortam değişkenleri

| Değişken | Varsayılan | Etki |
|---|---|---|
| `WARGAME_HOST` | `127.0.0.1` | yayınlanan arayüz (üretimde `0.0.0.0` + firewall) |
| `WARGAME_PORT` | `2222` | yayınlanan SSH portu |
| `WARGAME_HOSTNAME` | `localhost` | oyuncuya basılan host adı |
| `WARGAME_EPOCH` | `dev` | mühür dönemi |
| `WARGAME_SECRET_FILE` | `./docker/secrets/wargame_secret` | sır dosyası |
| `WARGAME_SECRET` | — | base64 sır (dosya yerine) |
| `WARGAME_SUBNET` | `172.28.0.0/16` | konteyner alt ağı (firewall kuralı için) |
| `WARGAME_DISABLE_SUID` | `0` | `1` ise SUID/SGID yazılmaz (sertleştirilmiş profil) |
| `WARGAME_LEVELS` | `/opt/wargame/levels` (imaj) | seviye klasörü |

---

## 4. Oyun içi komut aileleri (oyuncu)

Her seviye **tek bir aile** öğretir. Aşağıdaki tablo hangi komutun hangi
seviyede *neden* kullanıldığını gösterir — sözdizimi değil, amaç.

| Aile | Komutlar | Seviye | Amaç |
|---|---|---|---|
| Gezinme & okuma | `pwd`, `ls -la`, `cat`, `file` | 00, 03, 06, 10, 11 | durumu görmek; uzantıya değil içeriğe güvenmek |
| Metin arama | `grep -r`, `grep -E`, `awk` | 01, 04 | dizinde ve yapılandırılmış log'da satır/alan seçmek |
| Kodlama | `base64 -d` | 01 | "gizlenmiş" görünenin çoğu zaman yalnızca *kodlanmış* olduğunu görmek |
| İzin & ayrıcalık | `ls -la`, `find -perm -4000`, `getfacl` | 02 | çalıştıranın değil **sahibin** kimliğiyle çalışan dosya |
| Dosya bulma | `find -size`, `-user`, `-type` | 03 | iki filtrenin birleşimiyle arama uzayını daraltmak |
| Arşiv katmanları | `file`, `tar -ztvf/-xzvf`, `-j`, `-J` | 06 | sıkıştırma ile arşivlemenin ayrı işler olduğunu görmek |
| Zamanlanmış işler | `ls /etc/cron.d`, `cat`, `crontab -l` | 05, 07, 08, 09 | senin başlatmadığın ama senin adına çalışan işler |
| Süreç & ortam | `ps aux`, `/proc/<pid>/environ`, `tr`, `strings` | 08 | sırrın dosyada değil, bir sürecin ortamında olması |
| Yerel servis | `ss -tulpn`, `curl`, `nc` | 07 | yalnızca loopback'te dinleyen bir kapıyı bulmak |
| Yetki devri | `sudo -l`, `sudo -n -u`, GTFOBins (`find -exec`) | 09 | "dar görünen" kuralın aslında geniş olduğunu görmek |
| Paket analizi | `tcpdump -r`, `-A`, `strings` | 10 | metin olmayan kayıttan metin çıkarmak |
| İkili analiz | `objdump -d`, `ltrace -e strcmp`, `gdb break strcmp` | 11 | sırrın bellekte düz metin olarak yaşadığını görmek |

### Seviye → mekanizma matrisi

| Seviye | Ad | Mühür nerede durur | Nasıl açığa çıkar |
|---|---|---|---|
| 00 | Eşik | `~/welcome.txt` içinde düz | `cat` |
| 01 | Defter | `~/ledger/2026-10-03.md` içinde **base64** | `grep -r` + `base64 -d` |
| 02 | Mühür Okuyucusu | `/etc/wargame/pass/03` | SUID okuyucu **veya** ACL |
| 03 | Kasa Araması | `/srv/vault/04/manifest.dat` | `find -user player03 -size 4096c` |
| 04 | Kayıt Okuma | `1996-transfer.log` içinde tek satır | `grep -E` / `awk` |
| 05 | Kendiliğinden | cron işinin çıktısı `/var/spool/wargame/05/seal.log` | cron dosyasını oku + çıktıyı yakala |
| 06 | Katmanlar | iç içe `seal.tar.bz2` içinde | `tar -ztvf` → `-xzf` → `-xjf` |
| 07 | Kapalı Kapı | loopback servisi (127.0.0.1:8080) | `ss -tulpn` + `curl`/`nc` |
| 08 | Görünmez Yolcu | çalışan sürecin ortamı | `ps` + `/proc/<pid>/environ` |
| 09 | Dar Kapsam | `player10`'un dosyası | `sudo -l` + `find -exec` **veya** ayrıcalıklı iş |
| 10 | Kayıt Altında | `capture.pcap` içinde HTTP | `tcpdump -r -A` / `strings` |
| 11 | Kuşatılmış Sır | `~/lib/blob`, 0x5A ile XOR'lu | `objdump`/`ltrace`/`gdb` |

---

## 5. Oyuncu hızlı başvuru (spoiler'sız)

İlk beş dakika:

```bash
pwd                 # neredeyim?
ls -la              # ne var, izinler ne?
cat DOSYA           # oku
file DOSYA          # uzantıya güvenme, türü sor
grep -rn KALIP .    # dizinde ara
find / -user $(id -un) -type f 2>/dev/null   # bana ait olanlar
```

Sık kullanılan sözdizimi:

```bash
ls -la                       # uzun liste + gizli girişler
find / -size 4096c -type f 2>/dev/null        # tam 4096 bayt ('c' = bayt)
tar -ztvf arsiv.tar.gz       # listele (gzip); -j = bzip2, -J = xz
ss -tulpn                    # dinleyen soketler
ps aux | grep "$(id -un)"    # benim süreçlerim
tr '\0' '\n' < /proc/<PID>/environ            # ortamı okunur yap
sudo -l                      # bana verilen kurallar
tcpdump -r kayit.pcap -A     # paket yüklerini ASCII bas
```

**Not:** her seviyenin mührü 20 karakterlik küçük harf+rakam dizisidir ve
`/etc/wargame/pass/NN` altında `0400` izinle durur — yani yalnızca sahibi okur.

---

## 6. Çıkış kodları

| Kod | Anlam | Kaynak |
|---|---|---|
| `0` | başarı | tüm komutlar |
| `1` | denetimde `error` seviyesinde bulgu | `audit` |
| `2` | şema/sır/materyalizasyon/istatistik hatası | tüm komutlar (`LevelError`, `SecretError`, `ProvisionError`, `StatsError`) |

> `python -m wargame.provision` modülü doğrudan çalıştırılırsa (konsol yerine)
materyalizasyon hatası `1` döner; `python -m wargame provision` yolu hatayı `2`
olarak raporlar.

Hatalar `stderr`'e `hata: …` biçiminde yazılır; stdout makine tarafından
okunabilir kalır (`flag`, `stats --json`).

---

## 7. İşletim komutları (bakımcı)

```bash
# Seviye ekleme
make new-level ID=12 TITLE="Yeni Seviye"
$EDITOR levels/12-yeni-seviye/level.yml
make check && make test

# Tek seviyeyi uçtan uca kanıtla (çözüm dosyası varsa)
make validate LEVEL=03

# Sertleştirilmiş profile karşı doğrula
make validate-hardened

# Tüm parolaları döndür (eski mühürler ölür)
make rotate EPOCH=2027Q1

# Yeni sır + yeni dönem + sıfırdan konteyner
make rotate-epoch EPOCH=2027Q1

# Çalışan sandbox'ta sızıntı denetimi
make audit
```

---

## 8. Spoiler politikası

- `docs/levels/NN.md` sayfaları **çözüm içermez**; yöntemi anlatır.
- `level.yml` içindeki `hints` üç kademe verir: daralt → işaret et → neredeyse
  söyle. Yine de tam komut satırını vermez.
- `solutions/NN.sh` commit **edilmez** (`.gitignore`), CI'da özel depodan gelir.
- Bir katkı, çözümü oyuncu build'ine koyuyorsa birleştirilmez
  (`CONTRIBUTING.md` kontrol listesi).
