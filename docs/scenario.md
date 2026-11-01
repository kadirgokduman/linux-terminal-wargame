# wargame — Senaryo ve Bulmaca Dizilimi

> Bu belge oyunun **tam hikâye akışını ve bulmaca dizilimini** tek yerde toplar.
> Kapsam: çerçeve, perde yapısı, seviye başına anlatı vuruşu ve bulmaca,
> mühür zinciri ve bitiş. Bulmacaların *çözümü* burada yoktur (spoiler politikası:
> [`commands.md`](commands.md) §8, [`../CONTRIBUTING.md`](../CONTRIBUTING.md)).
>
> Durum: **taslak / v0.1.** İlgili belgeler: [`architecture.md`](architecture.md),
> [`commands.md`](commands.md), [`levels/`](levels/).

---

## 1. Çerçeve

Oyuncu, kapanmakta olan bir arşivin terminaline bağlanır. Kimliği bir isim
değil bir **görev**tir: *custodian*. Arşiv, yerini koruyan ama kendisini
açıklamayan bir yerdir; onu ayakta tutan şey, açılmış mühürlerin sayısıdır.

```text
  ┌──────────────────────────────────────────────────────────────┐
  │  C A L D E R   R E A C H   ·   A R Ş İ V   T E R M İ N A L İ  │
  └──────────────────────────────────────────────────────────────┘

  Hoş geldin, custodian.
  Bu makinede iki şey var: kapanmakta olan bir arşiv ve onu
  kapatmaya çalışan bir sayaç. Mühürler açıldıkça arşiv nefes alır.
```

Üç anlatısal sabit:

1. **Zincir kimliktir.** İlerleme, bir kullanıcıdan diğerine geçmektir
   (`player00 → player01 → …`). Her mühür bir sonraki kapının anahtarıdır.
2. **Sır, gizlendiği yerde durmaz.** Mühürler dosyada, arşivde, ağ kaydında,
   süreç ortamında ya da bir ikilinin belleğinde olabilir. Hiçbiri depoda
   yazılı değildir; hepsi bir sırdan türetilir.
3. **Her şey kasıtlıdır.** İzinler, sahiplikler, zamanlanmış işler ve eksik
   dosyalar birer tasarım kararıdır (bkz. banner).

### Kanon bağlantısı (Sigillatus ile ortak zemin)

Bu fiction, `Sigillatus` evreninin **terminal katmanıyla** aynı isimleri
kullanır ve ondan türetilmiştir:

| Öğe | Bu repoda nerede | Sigillatus karşılığı |
|---|---|---|
| Calder Reach | `docker/banner`, `welcome.txt`, pcap host'u `repository.calder.example` | Calder Reach, Repository House |
| custodian | `welcome.txt`, `1996-transfer.log` (`actor=custodian`), pcap (`holder: custodian`) | oyuncu kullanıcısı `custodian` (UID/GID 1000) |
| Mühür (seal) | 12 mühür, `pass/NN`, mühür metinleri | 19 mühür (`M1`–`M19` / `SEAL-1`–`SEAL-19`) |
| 1996 | seviye 01, 04, 10, 11'in dosya adları ve kayıtları | Iris Marsh, 1996 kayıtlı posta sızıntısı |
| Arşiv/sayaç | banner, `welcome.txt` | the Repository |
| İpucu kademeleri | `level.yml` → `hints` (2–4 kademe) | Tabby 3 kademeli ipucu sistemi |

> **Not.** Bu belge, iki projenin *ortak kanonunu* erken sabitler. Ortak kısım
> (Calder Reach, custodian, mühür, 1996) tek bir yerden yönetilmeli; yalnızca
> biçim farklı kalmalı: `wargame` gerçek işletim sistemi üzerinde, `Sigillatus`
> simüle bir çalışma zamanında oynar.

---

## 2. Perde yapısı

12 seviye üç perdeye ayrılır. Her perde bir *soruyu* değiştirir:

```text
Perde I  — Eşik ve İz            (00–03)   "Bu makine nasıl çalışıyor?"
Perde II — Kayıt ve Gizli Kanallar(04–08)  "Burada ne oldu?"
Perde III— Kırılgan Sırlar        (09–11)   "Bunu kim, hangi yetkiyle yaptı?"
Bitiş     — Mühür 12                        "Kapıyı sen açtın."
```

| # | Perde | Seviyeler | Öğretilen dünya görüşü |
|---|---|---|---|
| I | Eşik ve İz | 00, 01, 02, 03 | Sistemi gözlemlemek; izin, sahiplik ve aramanın temeli |
| II | Kayıt ve Gizli Kanallar | 04, 05, 06, 07, 08 | Geçmişin yazılı, zamanlanmış ve ağsal izleri |
| III | Kırılgan Sırlar | 09, 10, 11 | Yetkinin göründüğünden geniş olması; gizlemenin güvenlik olmaması |

---

## 3. Seviye akışı

Aşağıdaki tablo tam dizilimdir. "Anlatı vuruşu" bölümün hikâyedeki işi,
"Bulmaca" oyuncunun çözdüğü problem, "Mühür" ulaşılan sonraki kapıdır.

### Perde I — Eşik ve İz (`00`–`03`)

| ID | Ad | Anlatı vuruşu | Bulmaca | Mühür | Kavram | ~dk |
|---|---|---|---|---|---|---|
| **00** | Eşik | Arşiv seni adınla değil görevinle karşılar; odada tek bir nesne vardır. | Karşılama dosyasını oku. | **01** | `pwd`, `ls -la`, `cat`, izinler | 3 |
| **01** | Defter | 2026'nın dört günlük defteri; biri diğerlerinden farklı bir "taşıyıcı" taşır. | Dizin ağacında farklı kaydı bul, kodlanmış bloğu çöz. | **02** | `grep -r`, `base64 -d` | 8 |
| **02** | Mühür Okuyucusu | Sahibi başka biri olan, ama senin çalıştırabildiğin bir araç bekler. | Ayrıcalık taşıyan dosyayı bul ve mührü onun izniyle oku. | **03** | SUID, `find -perm -4000` (yedek: ACL) | 12 |
| **03** | Kasa Araması | Dört odalı kasa; bütün kayıtlar aynı genişlikte. | Boyut **ve** sahiplik filtresini birlikte kullan. | **04** | `find -size`, `-user` | 12 |

### Perde II — Kayıt ve Gizli Kanallar (`04`–`08`)

| ID | Ad | Anlatı vuruşu | Bulmaca | Mühür | Kavram | ~dk |
|---|---|---|---|---|---|---|
| **04** | Kayıt Okuma | 1996 taşıma günlüğü; tek bir satır hem seni hem mührü adlandırır. | İki koşulu birden sağlayan satırı alan bazlı seç. | **05** | `grep -E`, `awk` | 10 |
| **05** | Kendiliğinden | Senin başlatmadığın bir iş, senin adına çıktı üretiyor. | Zamanlanmış işi bul ve çıktısını yakala. | **06** | `cron`, `/etc/cron.d`, çıktı yönlendirme | 12 |
| **06** | Katmanlar | 1996 offsite paketi; dış katman gzip, iç katman bzip2. | Arşivi katman katman listele ve aç. | **07** | `file`, `tar -ztvf/-xzvf`, bzip2 | 15 |
| **07** | Kapalı Kapı | Dışarıya hiçbir şey açık değil; içeride bir kapı dinliyor. | Loopback servisini bul ve konuş. | **08** | `ss -tulpn`, `curl`, `nc` | 12 |
| **08** | Görünmez Yolcu | Mühür dosyada değil; onu taşıyan, senin adına çalışan bir süreç var. | Süreci bul, ortamından mührü oku. | **09** | `ps aux`, `/proc/<pid>/environ`, `strings` | 12 |

### Perde III — Kırılgan Sırlar (`09`–`11`)

| ID | Ad | Anlatı vuruşu | Bulmaca | Mühür | Kavram | ~dk |
|---|---|---|---|---|---|---|
| **09** | Dar Kapsam | Bir yetki devri var, ama "dar tutulmuş" görünüyor. | Kuralın gerçekte ne kadar geniş olduğunu gör. | **10** | `sudo -l`, GTFOBins (`find -exec`) | 15 |
| **10** | Kayıt Altında | 1996 doğrulama trafiğinin kaydı; mühür paketlerin içinde düz metin. | Metin olmayan kayıttan metni çıkar. | **11** | `tcpdump -r`, `-A`, HTTP başlıkları | 12 |
| **11** | Kuşatılmış Sır | Doğrulayıcı bir blob'u çözüyor; mühür ne `strings`'te ne de düz metin. | İkilinin anahtarını ve bellekteki düz metni bul. | **12** | `file`, `objdump`, `ltrace`, `gdb`, XOR | 20 |

**Toplam:** 12 seviye, ~143 dakika (tasarım hedefi).

### Mühür zinciri

```text
00 ──mühür 01──▶ 01 ──mühür 02──▶ 02 ──mühür 03──▶ 03 ──mühür 04──▶
04 ──mühür 05──▶ 05 ──mühür 06──▶ 06 ──mühür 07──▶ 07 ──mühür 08──▶
08 ──mühür 09──▶ 09 ──mühür 10──▶ 10 ──mühür 11──▶ 11 ──mühür 12──▶ ✦
```

`player12` son kullanıcıdır; mühür 12 oyuna giriş değil, **kapanış** olarak
tasarlanmıştır (bkz. §4 ve [`levels/12.md`](levels/12.md)). Motor, son
seviyenin ötesinde bir "final" kimliği ve mührü de üretir
(`provision.py`: `ids = 0..last+1`).

---

## 4. Bitiş

Mühür 12 okunduğunda anlatı tek bir cümleye iner:

> Arşiv kapandı. Onu senin açtığın kadar açık kaldı.

Bu satır, kapanış terminalinin **kanonik** metninin parçasıdır. Tam mesaj,
üç kapanış vuruşu ve metnin bugün nerede yaşadığı:
[`levels/12.md`](levels/12.md). Metin, oyunu açan cümleyi (`welcome.txt`)
geri verir ve son kimlikle (`player12`) girişte okunur.

Bu, `Sigillatus`'taki "künye sorusu"nun (bir arşiv, sahibi öldükten sonra kime
aittir?) terminal katmanındaki yankısıdır: cevap verilmez, açık bırakılır.

---

## 5. Anlatı kuralları (yazarlar için)

1. **Önce soru, sonra komut.** Seviye "şu komutu yaz" demez; bir problem verir.
2. **Tek kavram.** Bir seviye tek bir araç ailesi öğretir; ikincisi sonrakine.
3. **Ölü yok, hayalet yok.** Anlatı bir arşivin *durumundan* doğar; kimse
   oyuncuya seslenmez, kimse suçlanmaz.
4. **Kanıt, yorum değildir.** İmza, kayıt, paket ve iz gösterilir; hüküm verme.
5. **Spoiler inmaz.** `docs/levels/NN.md` yöntemi anlatır, çözümü vermez;
   `solutions/` hiç commit edilmez.
6. **Dış dünya yok.** Gerçek IP, gerçek kişi/kurum, gerçek ağ yok; tüm
   adresler belgeleme aralığındadır (`repository.calder.example`, `127.0.0.1`).

---

## 6. Bu belgenin sonraki adımları

- [ ] Perde başlarında kısa bir **ara sahne** metni (banner + birkaç satır).
- [ ] Her seviye için 3. kademe ipucu bir fikri tam kapatan cümleye indirilsin.
- [ ] `Sigillatus` ile ortak kanon tek dosyaya çıkarılsın (bu bölümün §1.1 tablosu
      oraya taşınır) ve iki proje ondan beslensin.
- [x] Bitiş metni `docs/levels/12.md` sayfasında kanonik olarak yazıldı
      (seviye 12 tanımı bilinçli olarak yok; final kimliği motorda üretilir).
- [ ] Kapanış metni konteynerden verilsin (bkz. `levels/12.md` §Uygulama durumu).
