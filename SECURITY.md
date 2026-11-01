# Güvenlik Politikası

## Kapsam

Bu depo iki şeyi birlikte barındırır: bir **oyun** ve onu çalıştıran
**sandbox**. Oyunun kuralları gereği oyunculara zayıf yapılandırılmış bir
makine sunulur; bu bir açık değildir.

Açık sayılan durumlar:

- Konteynerden ana sunucuya çıkış
- Bir seviyenin mührünün, o seviyeye gelmeden okunabilmesi
- `player*` dışındaki hesaplara erişim
- Konteynerden dış ağa çıkış
- Hizmet reddi (tek oyuncunun diğerlerini düşürmesi)
- `engine/` içinde komut enjeksiyonu veya yol kaçışı

Açık **sayılmayan** durumlar:

- Seviyedeki kasıtlı SUID/sudo yapılandırması (oyunun kendisi)
- Oyuncunun kendi kullanıcısı içinde yetki kazanması
- Zaten çözülmüş bir seviyenin parolasının bilinmesi

## Bildirim

Herkese açık bir issue açmayın. Depo sahibine özel kanaldan yazın
(GitHub Security Advisory tercih edilir).

Yanıt hedefi: 72 saat içinde ilk değerlendirme, 14 gün içinde düzeltme
planı. Düzeltme yayınlandıktan sonra, isterseniz adınızla birlikte
teşekkür edilir.
