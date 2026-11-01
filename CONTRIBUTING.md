# Katkı Rehberi

Bir seviye eklemek, bir cümle yazmaktan farksız olmalı. Bu rehber, bunu
mümkün kılan sözleşmeyi anlatır.

## İlkeler

1. **Önce soru, sonra komut.** Seviye "şu komutu yaz" demez; bir problem
   verir, komut o problemin cevabı olur.
2. **Tek kavram.** Her seviye tek bir şey öğretir: `grep`, `find`, SUID,
   cron, `base64`, `openssl`, `git`, `nc`… İkincisi bir sonraki seviyeye.
3. **Sıfır dış bağımlılık.** Bulmaca yalnızca imajda kurulu araçları
   kullanır ve dış ağa çıkmaz.
4. **Deterministik.** Aynı girdi her zaman aynı dosya sistemini üretir.
5. **Çözüm depoda değil.** `solutions/NN.sh` commit edilmez.

## Yeni seviye

```bash
make new-level ID=03 TITLE="Zamanlanmış İş"
```

Bu komut şunları üretir:

```
levels/03-zamanlanmis-is/
├── level.yml
└── files/README
docs/levels/03.md
solutions/03.sh        (git'e girmez)
```

### `level.yml` sözleşmesi

```yaml
id: "03"                     # iki hane, klasör adıyla aynı olmalı
slug: "zamanlanmis-is"       # klasör adının ikinci parçası
title: "Zamanlanmış İş"
concept: ["cron", "grep"]    # öğretilen kavramlar
requires: "02"               # yalnızca bir önceki seviye olabilir
estimated_minutes: 10

dirs:                        # isteğe bağlı, açık izinli dizinler
  - path: /home/player03/work
    owner: player03
    mode: "0750"

files:
  - path: /home/player03/work/README
    owner: player03
    mode: "0640"
    template: files/README   # veya content: | ya da source: /yol/binary
    pad_to: 4096             # sabit genişlik: find -size 4096c için

  - path: /usr/local/bin/helper
    owner: player04
    mode: "4755"             # SUID: sahibinin kimliğiyle çalışır
    source: /opt/wargame/bin/reader

cron:                        # @reboot, @daily … veya 5 alanlı zamanlama
  - user: root
    schedule: "@reboot"
    command: "/usr/local/lib/wargame/emit-04"

# Çalışma zamanında üretilen dosyalar (denetimde meşru sayılır)
expose:
  - /var/spool/wargame/03/seal.log

flag:
  owner: player03            # varsayılan: playerNN
  mode: "0400"               # varsayılan: 0400

hints:                       # en az 2 kademe
  - "Soruyu daraltan ipucu."
  - "Doğru komutu işaret eden ipucu."

docs: docs/levels/03.md
```

### Profil kapıları (`when:`)

Proje iki profilde çalışır: oynanabilir (`compose.yaml`, SUID açık) ve
sertleştirilmiş (`deploy/container-compose.yaml`, `WARGAME_DISABLE_SUID=1`).
`no_new_privs` altında SUID de dosya yetenekleri de işlemez; bu yüzden bir
seviye iki mekanizma taşıyabilir.

`files:`, `dirs:` ve `cron:` girdilerinde `when:` alanı kullanın:

| Değer | Ne zaman uygulanır |
|---|---|
| `always` (varsayılan) | her profilde |
| `suid-enabled` | yalnızca `WARGAME_DISABLE_SUID` kapalıyken |
| `suid-disabled` | yalnızca sertleştirilmiş profilde |

`acl:` bloğu ayrıcalığı POSIX ACL ile verir — NNP ile uyumlu tek yol.
`setcap` kullanmayın: NNP altında dosya yetenekleri de yok sayılır.

```yaml
acl:
  - path: /etc/wargame/pass/03
    user: player02
    perms: r                  # r | w | rw
    when: suid-disabled
```

Kural: her seviye **iki profilde de** çözülebilmelidir. SUID'ye dayanan bir
mekanizma ekliyorsanız yanına `when: suid-disabled` ile bir yedek koyun
(örnek: seviye 02 ACL, seviye 09 ayrıcalıklı iş).

### Arşivler

Mühür bir tarball içinde saklanacaksa `files` yerine `archives` kullanın.
Arşiv, materyalizasyon sırasında mühürle birlikte üretilir; depoda hiçbir
ikili dosya durmaz.

```yaml
archives:
  - path: /srv/archive/backup.tar.gz
    owner: player06
    mode: "0640"
    format: tar.gz                  # tar | tar.gz | tar.bz2 | tar.xz
    members:
      - name: MANIFEST
        content: |
          Serbest metin, mühür eklenebilir: {{flag:07}}
      - name: 1996/seal.tar.bz2     # iç içe arşiv
        format: tar.bz2
        members:
          - name: seal.txt
            template: files/seal.txt
```

Üretim deterministiktir (`mtime=0`, sıralı üyeler); `make restart`
aynı baytları üretir.

### Diğer üreticiler

| Alan | Ne üretir | Tipik araçlar |
|---|---|---|
| `pcaps:` | libpcap dosyası; mühür HTTP başlığında ve gövdesinde | `tcpdump -r -A`, `strings` |
| `encoding: xor` | dosya içeriğini 0x5A ile gizler | `objdump`, `ltrace`, `gdb` |
| `/etc/sudoers.d/*` | normal dosya (`0440`, root) | `sudo -l`, GTFOBins |

```yaml
pcaps:
  - path: /srv/pcap/capture.pcap
    owner: player10
    mode: "0640"
    host: repository.calder.example
    seal: "{{flag:11}}"
```

```yaml
  - path: /home/player11/lib/blob
    owner: player11
    mode: "0644"
    template: files/blob.txt
    encoding: xor          # text | xor
```

> `encoding: xor` gizlemedir, şifreleme değildir. Yalnızca "gizleme
güvenlik değildir" dersini veren seviyelerde kullanın.

### Zamanlanmış işler ve servisler

`cron` girdileri seviye kullanıcısı, `root` ya da **bir sonraki** kullanıcı
adına koşabilir. Uzun ömürlü bir servis gerekiyorsa `@reboot` kullanın:
cron, konteyner açılışında işi başlatır ve süreç ayakta kalır.

```yaml
cron:
  - user: player08              # servis, mührün sahibi adına çalışsın
    schedule: "@reboot"
    command: "/usr/local/lib/wargame/serve-08"
```

Servis betiği mühür **değerini** içermemeli; mührü çalışma anında kendi
sahibinin izniyle okumalı (`/etc/wargame/pass/NN`).

### Şablon değişkenleri

| Değişken | Değer |
|---|---|
| `{{user}}` | dosyanın sahibi (`player03`) |
| `{{level}}` | `03` |
| `{{flag}}` | bu seviyenin ürettiği mühür (`pass/04`) |
| `{{flag:05}}` | açıkça belirtilen mühür |
| `{{flag:05\|b64}}` | base64 kodlu hâli |
| `{{flag:05\|hex}}` | hex kodlu hâli |

**Kural:** bir seviye yalnızca *bir sonraki* mührü açığa çıkarabilir.
`{{flag:09}}` yazarsanız `make check` reddeder. Bu, "ileri atlama"
sızıntılarını yapısal olarak engeller.

## Kontrol listesi

Birleştirme isteği açmadan önce:

- [ ] `make check` geçiyor
- [ ] `make test` geçiyor
- [ ] `solutions/03.sh` yazıldı ve `make validate LEVEL=03` PASS verdi
- [ ] Seviye, hiç çözüm görmemiş iki kişi tarafından oynandı
- [ ] Süre hedefi tutuyor (5–15 dakika)
- [ ] `docs/levels/03.md` çözüm içermiyor
- [ ] İpuçları üç kademeli: daralt → işaret et → neredeyse söyle
- [ ] Dış ağ, gerçek IP, gerçek kişi/kurum adı yok
- [ ] Renk tek başına anlam taşımıyor (erişilebilirlik)

## İnceleme süreci

1. **Teklif** — `level-proposal` şablonuyla issue açın: kavram, hedef,
   taslak çözüm, tahmini süre.
2. **Taslak** — bir bakımcı kavramın müfredata uyduğunu onaylar.
3. **Uygulama** — PR: `level.yml`, dosyalar, `docs/levels/NN.md`.
4. **Oynanış testi** — iki bakımcı çözümü görmeden oynar; takıldıkları
   yer ipucu metnine dönüşür.
5. **Birleştirme** — CI yeşilse ve iki onay varsa.

## Commit biçimi

```
level(03): cron ile zamanlanmış mühür

Oyuncu, kendi crontab'ında çalışan bir betiği okumayı öğreniyor.
```

## Güvenlik

Bir güvenlik açığı bulduysanız issue açmayın; [`SECURITY.md`](../SECURITY.md)
(kapsam ve bildirim kanalı) dosyasındaki yolu izleyin.
