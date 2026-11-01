# wargame → Sigillatus — Strateji ve Yol Haritası

> İki projenin karşılaştırması, ortak modüller, hikâye entegrasyonu ve
> "önce `wargame`'i bitirip yayınla, sonra `Sigillatus`'a taşı" kararının
> gerekçesi. İlgili belgeler: [`architecture.md`](architecture.md),
> [`scenario.md`](scenario.md), [`commands.md`](commands.md).

---

## 1. İki proje bir bakışta

| | **`wargame/`** | **`Sigillatus`** |
|---|---|---|
| Tür | SSH/CTF wargame (gerçek sistem) | Terminal + görsel roman (ana oyun) |
| Çalışma zamanı | Docker + gerçek Linux + sshd + cron | Unity 2D URP, simüle çalışma zamanı |
| Dil | Python (motor) + YAML + sh/C | C# (`Sigillatus.*`) |
| Oyuncu kimliği | `player00 → player11` zinciri | tek `custodian` (UID/GID 1000) |
| Arayüz | çıplak kabuk | %60 CRT terminal + %40 VN panel + HUD |
| İçerik | 12 seviye, bildirimsel `level.yml` | 26 bölüm, JSON dil paketleri (`en`/`tr`) |
| Mühür | 12 mühür, `/etc/wargame/pass/NN` | 19 mühür (`M1`–`M19`) |
| İlerleme ölçüsü | giriş kaydı / skor tablosu | **Trace** + **Memory Ledger** + 4 son |
| Ön koşul | Docker + Docker Compose | Windows/macOS/Linux masaüstü |
| Yayın biçimi | `pip` paketi + OCI imajı | Unity build (mağaza) |
| Bugünkü durum | **çalışır** (12 seviye, CI, sertleştirilmiş profil) | **tasarım + doküman** (C# kodu yok) |

**Kritik gözlem.** Bugün elle tutulur, yayınlanabilir tek artefakt `wargame`'dir.
`Sigillatus`'ta henüz çalışan kod yok; ama içerik ve mimari tasarımı olgun.
Bu asimetri, sıralamayı belirler.

---

## 2. Farklar (neyi neden ayrı tutuyoruz)

| Eksen | `wargame`'in seçimi | `Sigillatus`'un seçimi | Neden ayrı |
|---|---|---|---|
| Gerçeklik | gerçek işletim sistemi, gerçek araçlar | simülasyon | gerçek araç = gerçek öğrenme; simülasyon = taşınabilirlik |
| İzolasyon | konteyner + capability düşürme | kum havuzu yok (her şey simüle) | farklı tehdit modelleri |
| İlerleme | kimlik zinciri (SSH) | anlatı + mühür | farklı oyun döngüleri |
| Ölçek | 12 seviye, ~2.5 saat | 26 bölüm, 4–6 saat | ayrı prodüksiyon eğrileri |
| Bağımlılık | Docker şart | tek uygulama | farklı kitleler |
| İçerik biçimi | `level.yml` (operasyonel) | `levels.json` + locale | farklı tüketiciler |

---

## 3. Ortak modüller ve taşınabilirlik

Aşağıdakiler iki projede **aynı problemi** çözer; kod paylaşılmaz, **kalıp ve
kanon** paylaşılır.

| Modül / kavram | `wargame`'de | `Sigillatus`'ta | Taşınabilirlik |
|---|---|---|---|
| Seviye şeması | `model.py` + `level.yml` | `LevelRuntime` + `levels.json` | **Yüksek** (alan adları aynı kalabilir) |
| Mühür türetimi | `flags.py`: HMAC-SHA256 + base32, 100 bit, dönem etiketli | mühür/bayrak türetimi | **Yüksek** |
| İpucu kademeleri | `hints[]` (2–4 kademe) | Tabby 3 kademe + `HintService` | **Yüksek** |
| Sızıntı denetimi | `audit.py` (düz/base64/hex arama, izin karşılaştırma) | `SealMatrixTests` + denylist | **Yüksek** |
| İçerik değişmezleri | `tests/test_levels.py` (zincir, izolasyon, tek mühür) | `LevelCatalogTests` vb. | **Yüksek** |
| Komut aileleri | gerçek `coreutils` | `ICommand` kayıt defteri (simüle) | **Orta** |
| Determinizm | `mtime=0`, sıralı arşiv, idempotent yazım | VFS CoW, deterministik Jint | **Orta** |
| İlerleme kaydı | `progress.log` + `stats.py` | Memory Ledger + Trace | **Düşük–Orta** |
| Ayrıcalık modelleri | SUID, sudo, ACL, cron, `/proc` | yok | **Düşük** (yapısal olarak farklı) |
| Lore | Calder Reach, custodian, mühür, 1996 | aynı isimler + Iris/the Steward | **Yüksek** (tek kanondan yönetilmeli) |

**Sonuç.** Taşınabilirliği yüksek olan her şey **içerik ve güvenlik**
katmanıdır; düşük olan şey **işletim sistemi ilkelleri**dir. Bu yüzden
`wargame`'i önce bitirmek, `Sigillatus`'un en pahalı ve en riskli kısmını
(içerik + mühür güvenliği) erkenden doğrular.

---

## 4. Hikâye entegrasyonu

İki proje aynı evrende, aynı kelimelerle konuşuyor:

| Ortak sabit | `wargame`'de kanıt |
|---|---|
| Calder Reach | `docker/banner`, `welcome.txt`, `repository.calder.example` |
| custodian | `welcome.txt` ("Hoş geldin, custodian"), `1996-transfer.log` (`actor=custodian`), pcap (`holder: custodian`) |
| 1996 | seviye 01/04/10/11 dosyaları ve kayıtları |
| Mühür açtıkça arşiv yaşar | `welcome.txt`: "Mühürler açıldıkça arşiv nefes alır" |
| İpucu kademeleri | `level.yml → hints` |

**Öneri:** ortak kanon **tek dosyada** tutulsun (ör. `docs/canon.md` ya da
mevcut `Sigillatus` `LORE.md`'nin bir bölümü). `wargame` bu kanonun
*operasyonel/terminal* yüzü, `Sigillatus` *anlatısal* yüzü olur. Böylece
12 mühür ile 19 mühür çelişmez: aynı protokolün farklı kesitleri olur.

---

## 5. Neden önce `wargame`'i bitirip yayınlamalı?

1. **İçerik doğrulaması en pahalı kısımdır.** 12 seviyenin gerçek araçlarla
   oynanması, seviye tasarımı ve ipucu kalitesini *gerçek oyuncularla* test
   eder; `Sigillatus`'a taşınacak içerik böylece kanıtlanmış olur.
2. **Şema olgunlaşır.** `level.yml` alanları (`concept`, `hints`,
   `estimated_minutes`, `requires`, `flag`) `Sigillatus`'un `levels.json`
   şemasının doğal atasıdır; üretimde denenmiş olur.
3. **Mühür güvenliği kanıtlanır.** "Depoda flag yok + HMAC türetme + dönem
   rotasyonu" modeli sahada çalışır; `Sigillatus` bu dersi bedava devralır.
4. **Denetim kültürü kurulur.** `audit.py` (sızıntı arama) ve
   `docs/security.md`, `Sigillatus`'un anti-cheat/leak testlerinin şablonudur.
5. **CI/CD ve katkı süreci şablon olur.** `lint → test → hardening → build →
   solve` hattı ve `CONTRIBUTING.md` akışı büyük projeye kopyalanır.
6. **Kanon ucuz doğrulanır.** Calder Reach/custodian/mühür dili, aylar süren
   bir oyuna yatırım yapmadan önce gerçek oyunculara gösterilmiş olur.
7. **Hızlı ve görünür bir çıktı.** Haftalar içinde yayınlanabilir; depo
   itibarı, katkı ve geri bildirim döngüsü hemen başlar.
8. **Risk izole edilir.** `Sigillatus` kapsamı daralırsa `wargame` tek başına
   ayakta duran, tam bir proje olarak kalır.
9. **Yetenek hunisi.** `wargame`'e katkı veren seviye yazarları, doğal olarak
   `Sigillatus` seviye içeriğinin de kaynağıdır.
10. **Motivasyon ve tempo.** Küçük, bitmiş işler büyük projenin enerjisini
    korur; yayınlanmış bir v1.0, "devam ediyor" hissini somutlaştırır.

### Riskler ve azaltma

| Risk | Etki | Azaltma |
|---|---|---|
| İki çalışma zamanı birbirinden kopar | Kanon ve içerik çelişir | Ortak kanon dosyası + tek şema kaynağı |
| İki kod tabanı bakım yükü | Yavaşlama | `wargame` = içerik laboratuvarı; `Sigillatus` = simülasyon |
| 12 ↔ 19 mühür tutarsızlığı | Anlatı kafa karışıklığı | `wargame`'i protokolün "terminal kesiti" olarak konumla |
| `wargame` yayını sürüncede kalır | Fırsat kaçar | Yayını **zaman kutusuna** al: lisans + README + etiket (Faz 0) |
| Kapsam kayması (CLI'ya tam simülasyon) | Aylarca sapma | Standalone CLI opsiyonel bırakılır (bkz. §6) |

---

## 6. Yol haritası

```text
Faz 0  Yayın hazırlığı            (günler)   README, dokümanlar, etiket, rozetler
Faz 1  İçerik cilası              (günler)   kapanış (seviye 12), perde metinleri, ipuçları
Faz 2  (Ertelendi) Yerel CLI      (haftalar)  wargame play --local  [Seçenek A]
Faz 3  Sigillatus'a port          (haftalar)  şema adaptörü + ortak kanon + kalıplar
Faz 4  (Ertelendi) Ortak çekirdek (aylar)    tam simülasyon [Seçenek B]
```

> **Karar (2026-10-28):** yayın için **Seçenek C** seçildi — Docker Compose +
> SSH kanonik çalışma ortamı olarak kalır, motor refactor edilmez. Bu yüzden
> Faz 2 ve Faz 4 "ertelendi" durumundadır: kapsam dışı değil, sırası
> gelmemiş. Gerekçe: [`architecture.md`](architecture.md) §9.

| Faz | Çıktı | Ölçüt |
|---|---|---|
| **0** | `LICENSE`, yayın README'si, `v0.1.0` etiketi | Depo klonlanır, `make up` çalışır, README doğru |
| **1** | tam 12 seviye + perde metinleri | `make check && make test` yeşil; iki oyuncu bitirir |
| **2** | `wargame play --local` (Docker'sız, kısıtlı) | Docker olmadan 03, 04, 06, 10, 11 oynanır |
| **3** | `Sigillatus` `levels.json` üreteci + ortak kanon | Bir `level.yml` → bir oyun bölümü |
| **4** | paylaşılan simülasyon çekirdeği | Aynı içerik iki çalışma zamanında koşar |

---

## 7. Karar noktaları (netleşmesi gerekenler)

1. **Lisans.** `LICENSE` yok; README bunu "TBD" olarak işaretliyor. Yayın için
   seçim şart (kod için MIT/Apache-2.0; içerik/metin için ayrı bir lisans
   düşünülebilir).
2. **README dili.** Proje tümüyle Türkçe; uluslararası kitle için İngilizce özet
   ya da çift dilli README eklenmeli mi?
3. **Standalone CLI — karara bağlandı (2026-10-28).** Docker Compose + SSH
   kanonik ortam olarak kalır; **Seçenek C** uygulanır, sanal CLI yazılmaz.
   A/B ertelendi. Gerekçe ve kapsam sınırı:
   [`architecture.md`](architecture.md) §9 (Karar).
4. **`Sigillatus` içindeki rolü.** `wargame` ana oyunun *prequel*'i mi,
   *yan kanalı* mı, yoksa içerik *test düzeneği* mi? Bu, kanonun nasıl
   bağlanacağını belirler.
5. **İçerik sahipliği.** Seviye metinleri tek yerde mi yazılsın (paylaşılan
   kanon) yoksa her proje kendi yazarlarını mı beslesin?

---

## 8. Öneri (özet)

**Faz 0 + Faz 1'i şimdi yap, Faz 3'ü `Sigillatus` kodlaması başladığında aç.**
(Faz 2 ile Faz 4 karara bağlandı: ertelendi — bkz. §6 karar notu.) Gerekçe: `wargame` bugün yayınlanabilir bir
proje; onu bitirmek `Sigillatus`'un en riskli iki varlığını (içerik ve mühür
güvenliği) erkenden doğrular, geri kalan kod yazımını bekletmeden değer üretir.
