# ⚡ MekanBot — Production-Ready Discord Asistanı & Yönetim Sistemi

MekanBot; sokak ağzıyla konuşan, yapay zeka (LLM) destekli, asenkron SQLite veritabanı altyapısıyla çalışan ve sunucunun altını üstüne getiren çok modüllü bir Discord botudur. Sabit kanal ID'leri veya RAM hafızalarla uğraşmaz; her şeyi `!kurulum` komutuyla dinamik olarak yönetir.

---

## 🚀 Öne Çıkan Özellikler
* **Asenkron Veritabanı (`aiosqlite`)**: Ekonomi, seviye ve sunucu ayarları kalıcı olarak SQLite veritabanında saklanır[cite: 3].
* **Dinamik Kanal Yönetimi**: Sabit ID devri bitti; `!kurulum` komutu ile log, oyun, müzik, sohbet ve admin kanalları sunucuya özel olarak atanır[cite: 3].
* **LLM Destekli Sohbet & Destek**: Kullanıcıların kişisel hafızasını tutan yapay zeka chatbotu ve ticket sisteminde otomatik çözüm üreten yapay zeka asistanı[cite: 3].
* **Kapsamlı Moderasyon & Anti-Nuke**: Otomatik küfür/reklam filtresi, sosyal kredi sistemi, ghost-ping avcısı ve sunucu patlatma (nuke) koruması[cite: 3].
* **Kumarhane & Satranç**: Gerçek zamanlı bahisli Blackjack, Slot makineleri ve Chess.com entegreli dinamik satranç tahtası[cite: 3].
* **Müzik Sistemi (`yt-dlp`)**: YouTube üzerinden kesintisiz müzik akışı, kuyruk (queue) yönetimi ve otomatik yeniden bağlanma[cite: 3].
* **Otomatik Yedekleme (Backup)**: Sunucunun rollerini ve kanallarını JSON olarak yedekleyen, gerekirse kıyamet protokolüyle sıfırdan kurabilen sistem[cite: 3].

---

## 🕹️ Komut Rehberi ve Kullanım

### 1. Kurulum Komutları (Admin)
* **`!kurulum`**
  * *Açıklama*: Botun çalışacağı temel kanalları (Log, Oyun, Müzik, Sohbet, Admin) sırayla sorar ve veritabanına kaydeder[cite: 3]. Sadece `Yönetici (Administrator)` yetkisi olanlar kullanabilir[cite: 3].

### 2. Genel & Yardımcı Komutlar
* **`!feedback <mesaj>`** (Alternatifler: `!geri_bildirim`, `!oneri`, `!istek`)
  * *Açıklama*: Bot veya sunucu hakkında istek/önerilerini yazar; mesajın doğrudan mekanın sahibinin (senin) DM kutusuna düşer[cite: 3].

### 3. Ekonomi & Kumarhane (`game_channel` içinde çalışır)
* **`!bakiye`** (Alternatifler: `!cüzdan`, `!para`)
  * *Açıklama*: Cüzdanındaki toplam bakiyeyi gösterir[cite: 3].
* **`!maaş`**
  * *Açıklama*: Belirli aralıklarla (6 saatte bir) maaşını çekmeni sağlar[cite: 3].
* **`!blackjack <bahis>`** (Alternatif: `!bj`)
  * *Açıklama*: Kasaya karşı interaktif butonlarla Blackjack (21) oynamanı sağlar[cite: 3].
* **`!slot <bahis>`** (Alternatif: `!kumar`)
  * *Açıklama*: Slot makinesini döndürür, şanslı rakamları yakalarsan paranı katlar[cite: 3].

### 4. Satranç Sistemi (`game_channel` içinde çalışır)
* **`!satranç @Kullanıcı <bahis>`**
  * *Açıklama*: Etiketlediğin kişiye parasını ortaya koyarak satranç meydan okuması yollar[cite: 3].
* **`!hamle <hamle>`** (Örn: `!hamle e4`, `!hamle Nf3`)
  * *Açıklama*: Tahtada hamleni yapmanı sağlar[cite: 3].
* **`!pes_et`**
  * *Açıklama*: Gözün yemezse masadan kaçıp maçı rakibe bırakır[cite: 3].

### 5. Seviye Sistemi (`chat_channel` içinde çalışır)
* **`!seviye`** (Alternatifler: `!rank`, `!rütbe`, `!level`, `!lvl`)
  * *Açıklama*: Sunucudaki mevcut seviyeni, XP miktarını ve ilerleme çubuğunu gösterir[cite: 3].

### 6. Müzik Sistemi (`music_channel` içinde çalışır)
* **`!play <şarkı adı / link>`** (Alternatifler: `!p`, `!çal`, `!oynat`)
  * *Açıklama*: Ses kanalına katılır ve YouTube'dan müziği çalmaya (veya kuyruğa eklemeye) başlar[cite: 3].
* **`!skip`** (Alternatifler: `!s`, `!geç`, `!atla`)
  * *Açıklama*: Çalan parçayı atlayıp kuyruktaki sonraki şarkıya geçer[cite: 3].
* **`!queue`** (Alternatifler: `!q`, `!sıra`, `!liste`)
  * *Açıklama*: Mekanın o anki çalma listesini (kuyruğunu) gösterir[cite: 3].
* **`!leave`** (Alternatifler: `!sg`, `!ayrıl`, `!dur`)
  * *Açıklama*: Botu ses kanalından kovar ve kuyruğu temizler[cite: 3].

### 7. Moderasyon & Destek Komutları (`admin_channel` içinde çalışır)
* **`!kredi`**
  * *Açıklama*: Kendi sosyal kredi puanını ve sunucudaki durum özetini gösterir[cite: 3].
* **`!purge <miktar>`** (Alternatifler: `!temizle`, `!sil`)
  * *Açıklama*: Belirtilen miktarda mesajı kanaldan anında buharlaştırır (Max 100)[cite: 3].
* **`!mute @Üye <dakika> [sebep]`**
  * *Açıklama*: Geveze üyeleri belirli bir süre susturur (Timeout atar)[cite: 3].
* **`!zindan @Üye`**
  * *Açıklama*: Üyenin tüm rollerini alıp cezalı zindan rolünü basar[cite: 3].
* **`!ban @Üye [sebep]`**
  * *Açıklama*: Sunucunun huzurunu kaçıranı kalıcı olarak siktir eder[cite: 3].
* **`!ticket_kur`**
  * *Açıklama*: Kanala yapay zeka destekli destek talebi açma panelini kurar[cite: 3].
* **`!backup_al`**
  * *Açıklama*: Sunucunun iskeletini (roller, kanallar, kategoriler) anlık olarak yedekler[cite: 3].
* **`!backup_yukle`**
  * *Açıklama*: (Kıyamet Protokolü) Mevcut sunucuyu yıkıp yedekteki yapıyı yeniden inşa eder[cite: 3].

### 🤖 Yapay Zeka Sohbet Modu (`chat_channel` içinde çalışır)
* Botun bulunduğu kanalda ona etiket atarak (`@MekanBot`) veya mesajını yanıtlayarak dertleşebilirsin. Her kullanıcının son 5 mesajını ayrı ayrı hafızasında tutar, sokak ağzıyla ve serseri bir tavırla sana cevap verir[cite: 3].

---

## ⚙️ Kurulum ve Çalıştırma

1. Gerekli kütüphaneleri yükle:
   ```bash
   pip install -r requirements.txt