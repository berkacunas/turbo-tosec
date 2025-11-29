# 🚀 turbo-tosec

[![CI/CD](https://github.com/berkacunas/turbo-tosec/actions/workflows/release.yml/badge.svg)](https://github.com/berkacunas/turbo-tosec/actions/workflows/release.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPL_v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Latest Release](https://img.shields.io/github/v/release/berkacunas/turbo-tosec)](https://github.com/berkacunas/turbo-tosec/releases)

> **TOSEC veritabanlarını ışık hızında sorgulamak için DuckDB tabanlı, yüksek performanslı içe aktarma aracı.**

**turbo-tosec**, devasa **TOSEC (The Old School Emulation Center)** DAT koleksiyonunu tarar, ayrıştırır ve anında sorgulanabilir tek bir **DuckDB** veritabanı dosyasına dönüştürür.

Arşivciler ve retro oyun tutkunları için tasarlanan bu araç, yüz binlerce XML/DAT dosyasından oluşan yığınları, saniyeler içinde SQL ile sorgulanabilen modern bir formata çevirir.

-----

### 📥 Hemen İndir (Python Gerekmez)

Python kurmakla uğraşmak istemiyorsanız, işletim sisteminiz için hazır çalıştırılabilir dosyayı indirebilirsiniz:

  * **Windows:** [`turbo-tosec_v1.2.2_Windows.exe` İndir](https://www.google.com/search?q=%5Bhttps://github.com/berkacunas/turbo-tosec/releases/latest%5D\(https://github.com/berkacunas/turbo-tosec/releases/latest\))
  * **Linux:** [`turbo-tosec_v1.2.2_Linux.tar.gz` İndir](https://www.google.com/search?q=%5Bhttps://github.com/berkacunas/turbo-tosec/releases/latest%5D\(https://github.com/berkacunas/turbo-tosec/releases/latest\))

-----

## ⚡ Neden turbo-tosec?

  - **Hız Odaklı:** Maksimum veri işleme hızı için Python'un XML ayrıştırma gücünü DuckDB'nin "Toplu Ekleme" (Bulk Insert) yetenekleriyle birleştirir.
  - **Bağımlılık Yok:** Harici sunuculara (MySQL, Postgres) ihtiyaç duymaz. Çıktı, taşınabilir tek bir `.duckdb` dosyasıdır.
  - **Akıllı Tarama:** İç içe geçmiş alt klasörlerdeki binlerce `.dat` dosyasını otomatik olarak bulur (`recursive scan`).
  - **İlerleme Takibi:** `tqdm` aracılığıyla detaylı ve gerçek zamanlı ilerleme çubuğu sunar.

## 📦 Kurulum

Bu proje Python 3.x gerektirir.

```bash
git clone https://github.com/berkacunas/turbo-tosec.git
cd turbo-tosec
pip install -r requirements.txt
```

## 🛠️ Kullanım

### 1\. Veriyi Hazırlayın

Bu araç TOSEC DAT dosyalarını (metadata) işler. En güncel DAT paketini [Resmi TOSEC Web Sitesinden](https://www.tosecdev.org/downloads) indirin ve bir klasöre çıkartın.

### 2\. İçe Aktarıcıyı Çalıştırın

#### Standart Mod (Güvenli)

Hata ayıklama veya küçük koleksiyonlar için en iyisidir. Tek bir iş parçacığı (single thread) kullanır.

```bash
python tosec_importer.py -i "/dosya/yolu/TOSEC" -o "tosec.duckdb"
```

#### Turbo Mod (Çok İş Parçacıklı) 🔥

İşlemcinizin tüm gücünü serbest bırakın\! Tam TOSEC arşivini içe aktarmak için önerilir.

```bash
# 8 işçi thread ve daha büyük işlem (batch) boyutu kullanımı
python tosec_importer.py -i "/dosya/yolu/TOSEC" -w 8 -b 5000
```

#### Komut Satırı Argümanları

| Parametre | Açıklama | Varsayılan |
| :--- | :--- | :--- |
| `-i, --input` | DAT dosyalarını içeren kök dizinin yolu. | **Zorunlu** |
| `-o, --output` | Oluşturulacak DuckDB veritabanı dosyasının yolu. | `tosec.duckdb` |
| `-w, --workers` | Paralel ayrıştırma için kullanılacak iş parçacığı sayısı. | `1` |
| `-b, --batch-size`| Her veritabanı işleminde (transaction) eklenecek kayıt sayısı. | `1000` |
| `--no-open-log` | Hata oluştuğunda log dosyasını otomatik olarak **açma**. | `False` |

## ⚡ Performans

*Yaklaşık 3.000 DAT dosyası (1 milyon ROM kaydı) içeren bir veri seti baz alınarak yapılan test sonuçlarıdır.*

| Mod | İşçiler (Workers) | Süre |
| :--- | :--- | :--- |
| **Standart** | 1 | \~45 saniye |
| **Turbo** | 4 | \~15 saniye |
| **Turbo Max** | 8 | \~9 saniye |

> *Not: Performans, disk okuma hızı (Disk I/O) darboğaz oluşturana kadar işlemci çekirdek sayısıyla orantılı olarak artar.*

## 🔍 Örnek Sorgular (DuckDB / SQL)

Oluşturulan veritabanını **DBeaver**, **VSCode SQLTools** veya **Python** kullanarak açabilir ve aşağıdaki gibi sorgular çalıştırabilirsiniz:

**Doğrulanmış [\!] Commodore 64 Oyunlarını Bul:**

```sql
SELECT game_name, rom_name 
FROM roms 
WHERE platform LIKE '%Commodore 64%' 
  AND rom_name LIKE '%[!]%';
```

**Yerel Bir Dosyayı Doğrula (Hash ile):**

```sql
SELECT * FROM roms WHERE md5 = 'DOSYANIZIN_MD5_HASH_DEGERI';
```

## 📄 Lisans

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.

-----

## ❤️ Projeyi Destekleyin

turbo-tosec, bağımsız bir geliştirici tarafından geliştirilmekte ve sürdürülmektedir. Eğer bu aracı faydalı bulduysanız ve geliştirmeyi desteklemek (veya sadece hazır derlenmiş `.exe` için teşekkür etmek) isterseniz, bağış yaparak destek olabilirsiniz\!

\<a href="[https://github.com/sponsors/berkacunas](https://github.com/sponsors/berkacunas)"\>
\<img src="[https://img.shields.io/badge/Sponsor-GitHub-pink?style=for-the-badge\&logo=github-sponsors](https://img.shields.io/badge/Sponsor-GitHub-pink?style=for-the-badge&logo=github-sponsors)" height="50" alt="GitHub'da Sponsor Ol"\>
\</a\>

\<a href="[https://www.buymeacoffee.com/depones](https://www.buymeacoffee.com/depones)" target="\_blank"\>\<img src="[https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png](https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png)" alt="Buy Me A Coffee" style="height: 60px \!important;width: 217px \!important;" \>\</a\>

  * **Bu repoya yıldız verin\!** ⭐ Görünürlüğe çok yardımcı olur.

-----

*Yasal Uyarı: Bu proje herhangi bir TOSEC veritabanı dosyası veya ROM barındırmaz. Yalnızca TOSEC projesi tarafından sağlanan metadata dosyalarını işlemek için bir araç sunar.*

**Telif Hakkı © 2025 berkacunas & DeponesStudio.**