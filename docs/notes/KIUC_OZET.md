# KIUC devresi: ne kurduk, ne gördük, ne anladık

*Basit Türkçe özet, 3 Kasım 2026. Teknik ayrıntı, sayılar ve kayıtlı plan: [`docs/KIUC.md`](../KIUC.md).*

## 1. Nereden

Hocanın 20 Ekim'de gönderdiği NREL raporu: NREL/TP-5D00-94430 (Kasım 2025), osti.gov/biblio/3011876. Devre
raporun Şekil 41'i, değerler Tablo 14–15. Raporda model dosyası yok; değerleri biz girip PSCAD'de kurduk.

NREL, ABD'nin ulusal yenilenebilir enerji laboratuvarı. Raporun sorusu: hatayı jeneratör değil inverter beslediğinde
koruma röleleri hâlâ doğru karar veriyor mu?

## 2. Devre ne

Hawaii'deki Kauai adasının elektrik şirketi KIUC'un gerçek bir 57.1 kV hattı. Soldan sağa:

| parça | ne | nereden |
|---|---|---|
| şebeke | sert kaynak, arkasında eşdeğer hat (EQ) | rapor |
| BUS1 | ortadaki bara; 7.5 MVA hidro jeneratör (açık ya da kapalı) | rapor (jeneratörün iç değerleri bizim varsayımımız) |
| Hat 2 | BUS1 → BUS2, 4.6 mil; hatalar burada | rapor |
| BUS2 | 15 MVA inverter, trafo ile bağlı | rapor |
| R1, R2 | röleler; R1 BUS1'de, R2 inverter tarafında (BUS2'de), ikisi de Hat 2'ye bakıyor | rapor |

Çizim: `docs/figures/kiuc_pscad/kiuc_pscad_labelled.png`.

## 3. İnverter

Kendi grid-following inverterimiz (ortalama model, PSCAD'de kendi bloğumuz). Rapordan: 15 MVA, akım sınırı 1.2 pu,
çalışma noktası P 0.25 / Q 0.15 pu, iki I₂ modu. Bizim seçimimiz: modelin kendisi ve FRT kazancı K₁ = 4 (IEEE 2800
aralığı 2–6).

İki I₂ modu (I₂: dengesiz hatada çıkan negatif-bileşen akımı; yön rölesi buna bakıyor):
- **bastırılmış:** inverter I₂ vermiyor;
- **IEEE 2800:** I₂ = 5·V₂, V₂'nin 90° önünde, bir jeneratörün kendiliğinden verdiği gibi.

## 4. Ne yaptık

143 PSCAD koşusu, Python'dan otomatik (`src/kiuc.py`). Bir test 13 koşu: 1 hatasız koşu + 12 hata (3 yer: %5, %50,
%80 × 2 tip: A-toprak, B-C × 2 direnç: 0.01 ve 5 Ω; raporun hata listesinden). Test R2 için (hidro kapalı / açık,
inverter tam güçte), R1 için (hata arkasında / önünde) ve daha sıkı akım sınırıyla tekrarlandı; çoğu iki modla.
Aynı hatalar basit statik modelde de çözüldü.

## 5. Ne gördük

1. **I₂ bastırılınca** raporun yön elemanı (32Q/32QG) hiçbir hatada karar veremiyor, ne R2'de ne R1'de. Yanlış karar
   değil, karar yok.
2. **IEEE 2800 ile** her hatada doğru yön: R2'de ileri, R1'de geri.
3. **Statik model ile PSCAD** raporun elemanında her kararda aynı.
4. Ek: IEEE 2800'ün pozitif-bileşen reaktif akım desteği (FRT) bizim artımsal yön elemanımızı bastırılmış modda da
   düzeltiyor (çeyrek güçte her hatada, tam güçte yalnız toprak hatalarında).
5. Ek: hocanın küme testi (set test) bu devrede ne IEEE 2800'e ne δ'ya ihtiyaç duyuyor. Bu statik tasarım ve EMT'de
   nominal noktada, **δ enjekte edilmeden**; δ enjekte edilmiş EMT'de denenmedi.

## 6. Ne anladık

- Raporun bulgusu bizim inverterimizle de tutuyor: rölenin yön kararı, inverterin I₂'yi nasıl ayarladığına bağlı.
- Sorun rölede değil, inverterin ayarında: IEEE 2800 kuralı rölelerin beklediği akımı geri veriyor.
- Basit statik model bu devrede PSCAD'in yerine güvenle kullanılabiliyor (aynı kararlar).

## 7. Sınırlar

Tek devre, tek inverter (grid-following), tek çalışma noktası (EMT'de), temiz ölçüm. Raporun kendi akım sınırlayıcısı
faz akımını 2 pu'nun üstüne çıkarıyor (gerçekçi değil); daha sıkı sınırla (1.2 pu) kararlar aynı.

## 8. Sıradaki

Hocanın kalan istekleri: raporun grid-forming inverteri, sonra KIUC'a 3–5 inverter (bir kısmı grid-forming, bir kısmı
grid-following) ve şebekesiz, hepsi inverter olan durum. Plan: [`docs/KIUC_MULTI.md`](../KIUC_MULTI.md) (kiuc-multi
dalı, PR #70 incelemesi).
