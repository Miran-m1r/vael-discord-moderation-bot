# MekanBot

Pycord cog mimarisi kullanan, SQLite tabanlı ekonomi, moderasyon, müzik, destek, satranç ve kasa sistemi içeren Discord botu.

## Kurulum

1. Bağımlılıkları yükleyin:

   ```bash
   pip install -r requirements.txt
   ```

2. `.env` dosyasını oluşturun:

   ```env
   DISCORD_TOKEN=...
   OPENAI_API_KEY=...
   ALLOW_EXTERNAL_AI=false
   DATABASE_PATH=data/mekanbot.sqlite3
   ```

3. Botu başlatın:

   ```bash
   python main.py
   ```

İlk çalıştırmada veritabanı tabloları otomatik oluşturulur. Yönetici, kanal kısıtlamalarını tanımlamak için `!kurulum` komutunu kullanmalıdır.

`ALLOW_EXTERNAL_AI=true` açıkça ayarlanmadıkça sohbet ve ticket içerikleri harici yapay zekâ hizmetlerine gönderilmez. Etkinleştirildiğinde gönderilen içeriklerde bilinen token, parola ve yetkilendirme bilgileri redakte edilir.

## Komutlar

### Kasa ve envanter

Kasa ve envanter komutları kurulumda belirlenen oyun kanalında kullanılabilir:

- `/cases`: Satın alınabilir kasaları listeler.
- `/buycase <kasa_adi>`: Bakiyeden kasa ücretini düşer; üç saniyelik kasa açılış animasyonundan sonra eşyanın adı, aşınma durumu, float değeri, fiyatı ve Steam Market görsel bağlantısını gösterir.
- `/inventory`: Envanteri sayfalı olarak gösterir.
- `/sell <item_id>`: Eşyayı fiyatı karşılığında satar.
- `/trade <kullanıcı> <item_id>`: Alıcının onaylayacağı takas teklifi oluşturur.

Kasa oranları: Mil-Spec `%79.92`, Restricted `%15.98`, Classified `%3.19`, Covert `%0.64`, Rare Special Item `%0.26`.

### Satranç

- `/chess`: Bota karşı satranç başlatır.
- `/chess <rakip> <bahis>`: Bir kullanıcıya davet gönderir; davet, `Kabul Et` veya `Reddet` düğmesiyle yanıtlanır.
- `/pes`: Devam eden oyundan ayrılır.

Hamleler, `Hamle Yap` düğmesinin açtığı modal üzerinden SAN veya UCI formatında girilir.

### Yardım

- `/help`: Botun ekonomi, kasa, envanter, satranç, müzik ve destek komutlarını listeler.
