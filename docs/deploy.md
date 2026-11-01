# Canlıya Alma Kılavuzu

Bu belge, oyunu tek bir VPS üzerinde anonim oyunculara açmak içindir.
Sırayı atlamayın: 5. adım (ağ izolasyonu) tamamlanmadan servisi
yayına almak, sunucunuzu açık bir kabuk servisi haline getirir.

## 0. Ön koşullar

| Gereksinim | Not |
|---|---|
| VPS | 2 vCPU / 4 GB RAM / 40 GB disk (Hetzner CX22, DO 4GB, vb.) |
| İşletim sistemi | Ubuntu 24.04 LTS veya Debian 12 |
| Docker | 27+ ve Compose v2 |
| git | depo erişimi |
| Alan adı | `wargame.example` (SSH için; IP ile de çalışır) |

Bellek tahmini: oynanabilir profil 1 GB, sertleştirilmiş profil 512 MB.
Aynı düğümde iki profili birlikte çalıştırmayın.

## 1. Kullanıcı ve temel sertleştirme

```bash
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
# SSH anahtarınızı deploy kullanıcısına kopyalayın, sonra:
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl reload ssh
```

Yönetim SSH'i yalnızca anahtarla. Oyuncu parolaları oyunun kendi
konteynerinde yaşar; düğümün SSH'i ile karışmaz.

## 2. Depo ve sır

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git make
sudo usermod -aG docker deploy && newgrp docker

# Depo adresinizi yazın: https://github.com/<owner>/wargame.git
git clone https://github.com/<owner>/wargame.git
cd wargame

# Sır: 32 bayt, base64. Depoya asla girmez (gitignore).
mkdir -p docker/secrets
head -c 32 /dev/urandom | base64 > docker/secrets/wargame_secret
chmod 600 docker/secrets/wargame_secret

cp .env.example .env
# .env içinde WARGAME_HOST=0.0.0.0 ve WARGAME_PORT=2223 yapın
```

Sırrı kaybederseniz oyuncuların parolaları kurtarılamaz — ama dönem
rotasyonu zaten tüm parolaları yeniler (bkz. §6).

## 3. İmaj

```bash
docker compose build            # ya da:
docker compose -f deploy/container-compose.yaml build
```

İmaj `debian:12-slim` üzerine kurulur; mühür **imajın içinde değildir**,
konteyner açılışında üretilir.

## 4. Ağ izolasyonu

Önce kuralı **kontrol edin**, sonra uygulayın:

```bash
sudo nft -c -f deploy/nftables.conf   # sözdizimi + çakışma kontrolü
sudo nft -f    deploy/nftables.conf
sudo nft list ruleset | head -40
```

Doğrulama (stack açıkken):

```bash
# Konteynerden dışarı çıkmayı deneyin — başarısız olmalı:
docker compose exec -T sandbox sh -c 'timeout 3 curl -sS https://example.com || echo "egress: engellendi"'

# Konteyner içi servisler hâlâ çalışmalı:
docker compose exec -T sandbox sh -c 'curl -s http://127.0.0.1:8080/seal | head -c 4'
```

> Uyarı: `input` zinciri `policy drop` ile çalışır. Yönetim SSH portunuz
> 22 değilse `deploy/nftables.conf` içindeki `tcp dport 22` satırını
> güncelleyin, yoksa sunucudan düşersiniz. Düşerseniz sağlayıcının
> web konsolundan `nft flush ruleset` çalıştırın.

## 5. Stack'i başlatma

```bash
docker compose -f deploy/container-compose.yaml up -d --build --wait
docker compose -f deploy/container-compose.yaml ps
```

Varsayılan olarak `127.0.0.1:2223` dinler. Dışarı açmak için `.env`
içinde `WARGAME_HOST=0.0.0.0` yapın; güvenlik duvarı zaten yalnızca
2222/2223 ve 22 portlarına izin verir.

İlk giriş:

```bash
docker compose -f deploy/container-compose.yaml exec -T sandbox \
  python3 -m wargame login 00
```

Bu komut **yönetici** çıktısıdır; oyuncular `player00` parolasını
duyuru sayfasından alır. Parolayı herkese açık bir yere yazıyorsanız
bilinçli olarak yapın: `player00` zaten herkese açık başlangıçtır.

## 6. Dönem rotasyonu

Sızan bir parola, dönem değişene kadar geçerlidir. Aylık rotasyon
önerilir:

```bash
scripts/rotate-epoch.sh 2027Q1
# sertleştirilmiş profil için:
scripts/rotate-epoch.sh --hardened 2027Q1
```

Betik: eski sırrı zaman damgasıyla yedekler, yenisini üretir, `.env`
dönemini günceller, konteyneri ve hacimleri silip yeniden kurar.
Sonuç: **tüm eski parolalar ölür**, skor tablosu (`logs` hacmi) da
sıfırlanır — istatistikleri saklamak istiyorsanız önce kopyalayın:

```bash
docker compose cp sandbox:/var/log/wargame/progress.log ./progress-$(date -u +%F).log
```

Sadece dönemi (sırrı değiştirmeden) döndürmek için:

```bash
make rotate EPOCH=2027Q1
```

## 7. Kaba kuvvet ve kötüye kullanım

| Katman | Ayar |
|---|---|
| sshd | `MaxAuthTries 3`, `MaxStartups 20:30:60`, `LoginGraceTime 20` |
| Parola entropisi | 100 bit (20 base32 karakter) — tahmin edilemez |
| Düğüm | `pids_limit`, `mem_limit`, `cpus`, `ulimits nproc` |
| Ağ | `deploy/nftables.conf` çıkış bloğu |
| Dış katman | fail2ban / CrowdSec (aşağıdaki filtre) |

fail2ban örneği (`/etc/fail2ban/jail.d/wargame.conf`):

```ini
[wargame]
enabled  = true
port     = 2223
filter   = sshd
logpath  = /var/lib/docker/containers/*/*-json.log
maxretry = 5
findtime = 10m
bantime  = 1h
```

Konteyner günlükleri JSON'dur; filtreyi buna göre uyarlamanız gerekir.
Alternatif: sshd günlüğünü `docker logs` yerine host'a yönlendirin.

## 8. Skor tablosu

Her başarılı giriş PAM üzerinden `/var/log/wargame/progress.log`
dosyasına yazılır. Özet:

```bash
make stats
# ya da:
docker compose exec -T sandbox python3 -m wargame stats
docker compose exec -T sandbox python3 -m wargame stats --json
```

Çıktı: seviye başına oturum sayısı, ilk/son giriş, aralık, en ileri
seviye ve zincirdeki kopukluklar.

## 9. İzleme ve veri saklama

```bash
docker compose logs -f --tail=100
docker stats --no-stream
df -h /var/lib/docker
```

- `progress.log` kişisel veri (IP) içerir. **30 gün** sonra silin.
- Konteyner günlükleri `10 MB × 3` ile sınırlıdır (compose tanımı).
- Oyuncu dosyaları `home` hacminde; yedeklenmesi gerekmez.

## 10. Yedekleme

Kalıcı olan tek şey depo ve sırdır:

```bash
tar -czf wargame-backup-$(date -u +%F).tgz \
  --exclude=.venv --exclude=node_modules . docker/secrets/wargame_secret
```

Sır yedeği olmadan konteyner yeniden kurulduğunda parolalar değişir
(ki bu genellikle istenen davranıştır).

## 11. Olay müdahalesi

| Durum | Yapılacak |
|---|---|
| Konteyner kaçışı şüphesi | Düğümü izole et, imajı yeniden derle, sırrı değiştir, dönemi döndür |
| Bir mühür sızdı | `scripts/rotate-epoch.sh <yeni-etiket>` — sızan parola anında ölür |
| Aşırı kaynak kullanımı | `docker stats`, `pids_limit` düşür, çıkış bloğunu doğrula |
| DDoS | Sağlayıcı koruması + `MaxStartups` + fail2ban |
| Hatalı seviye | `bash scripts/validate-all.sh` ile yeniden üret, düzeltmeyi yayınla |

## 12. Yayın kontrol listesi

- [ ] `docker/secrets/wargame_secret` üretildi, izni `600`, commit edilmedi
- [ ] `nft -c -f deploy/nftables.conf` temiz, kural yüklü
- [ ] `curl` ile dış çıkış testi **başarısız** (beklenen)
- [ ] `bash scripts/validate-all.sh` → 12/12 PASS
- [ ] `COMPOSE_FILE=deploy/container-compose.yaml bash scripts/validate-all.sh` → 12/12 PASS
- [ ] `python -m wargame audit` → yalnızca beklenen SUID uyarısı (sertleştirilmiş profilde 0 bulgu)
- [ ] `make stats` kayıt dosyasını okuyabiliyor
- [ ] Yönetim SSH'i anahtar tabanlı, parola kapalı
- [ ] Dönem rotasyonu takvime eklendi
- [ ] Log saklama süresi (30 gün) tanımlı
- [ ] README'deki başlangıç parolası (`player00`) yayınlandı
