# MekanBot Komut Rehberi

MekanBot, Pycord slash command mimarisi, asenkron SQLite veritabanı, ekonomi, moderasyon, müzik, ticket, satranç ve kasa sistemlerini bir arada sunar. Botta prefix (`!`) komutları kullanılmaz; tüm kullanıcı komutları Discord'un `/` menüsünde yer alır.

## Kurulum

- `/kurulum`: Yönetici yetkisine sahip kullanıcıların sunucu kanallarını yapılandırmasını sağlar.
- `/backup_al`: Sunucu yapısının yedeğini oluşturur.
- `/backup_yukle`: Sunucu yapısını sunucuya ait yedekten geri yükler.
- `/ticket_kur`: Yapılandırılmış ticket kanalına destek paneli gönderir.

## Genel ve ekonomi

- `/help`: Botta kayıtlı tüm slash komutlarını kategorilere göre listeler.
- `/feedback mesaj`: Yöneticiye geri bildirim veya öneri gönderir.
- `/bakiye`: Güncel kredi bakiyesini gösterir.
- `/maas`: Kullanılabilir maaş ödemesini hesabınıza aktarır.
- `/blackjack bahis`: Belirtilen bahisle blackjack başlatır.
- `/slot bahis`: Belirtilen bahisle slot oyunu başlatır.

## Kasa ve envanter

- `/cases`: Satın alınabilir kasaları listeler.
- `/buycase kasa_adi`: Kasa satın alır ve üç saniyelik açılış akışıyla eşya üretir.
- `/inventory`: Kullanıcının envanterini sayfalı biçimde görüntüler.
- `/sell item_id`: Eşyayı sistem fiyatından satar.
- `/trade kullanici item_id`: Onay gerektiren eşya transfer teklifi oluşturur.

## Satranç ve seviye

- `/chess`: Bota veya başka bir kullanıcıya karşı satranç oyunu başlatır.
- `/pes`: Devam eden satranç oyunundan ayrılır.
- `/seviye`: Kullanıcının XP ve seviye durumunu görüntüler.

## Müzik

- `/play arama_sorgusu`: YouTube üzerinden parça arar ve oynatır.
- `/skip`: Oynatılan parçayı atlar.
- `/queue`: Müzik kuyruğunu görüntüler.
- `/leave`: Botu ses kanalından çıkarır ve kuyruğu temizler.

## Moderasyon

- `/kredi`: Sosyal kredi puanını görüntüler.
- `/purge miktar`: Yönetim kanalındaki mesajları toplu olarak siler.
- `/mute uye dakika sebep`: Bir üyeyi belirtilen süreyle susturur.
- `/zindan uye`: Üyeye kısıtlama rolü tanımlar.
- `/ban uye sebep`: Bir üyeyi sunucudan uzaklaştırır.

Sohbet ve ticket LLM özellikleri için `.env` içinde `OPENAI_API_KEY` ve açıkça `ALLOW_EXTERNAL_AI=true` tanımlanmalıdır.
