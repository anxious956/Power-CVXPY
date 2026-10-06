# Sorular ve cevaplar

Proje hakkında sorulan sorular ve sade cevapları. Her cevap repodaki kayda (commit geçmişi,
`docs/PLAN.md`, `REVIEW.md`, `results/`) dayanır; kaynak her cevabın sonunda yazılı.

---

## 1. Hedefimiz ML ile koruma sistemi yapmaktı da, istediğimiz doğruluğu alamayınca mı CVXPY'ye geçtik?

**Hayır, sıra tam tersi.** Proje CVXPY ile başladı, ML sonradan eklendi. İkisi birbirinin yerine
geçen iki yöntem de değil, farklı işler yapıyorlar.

**Projenin asıl fikri (baştan beri):** Prof. Taylor'ın yöntemi. İnvertörlü şebekelerde klasik
mesafe rölesi arızayı iyi göremiyor, çünkü invertör arıza akımını sınırlıyor. Taylor'ın önerisi:
arıza anında invertöre küçük, **bilerek tasarlanmış bir sinyal** (yardımcı sinyal, δ) enjekte
ettirmek. Bu sinyal, röledeki ölçümü "hat içi arıza" ile "hat dışı arıza" arasında ayırt edilebilir
hale getirecek şekilde seçiliyor.

**CVXPY'nin rolü:** bu sinyali **tasarlamak**. "Hangi δ'yı enjekte edersem, ölçüm hataları ve
bilinmeyenler ne olursa olsun, her hat içi arıza her hat dışı arızadan ayrılır?" sorusu bir
optimizasyon problemi. CVXPY bunu çözüyor ve cevabı bir **garanti** olarak veriyor, deneme yanılma
olarak değil. Taylor'ın yöntemini diğerlerinden ayıran şey de bu garanti.

**ML'in rolü:** kararı vermek. Röleye gelen dalga şeklinden "açayım mı, açmayayım mı" demek. İki
yerde kullanıldı:
- sentetik veride "yardımcı sinyal öğrenen bir dedektöre yardım ediyor mu?" sorusu için;
- gerçek EMT verisinde (EvEMTBench) "öğrenen model klasik zone-1 kuralından iyi mi?" sorusu için.

**Zaman sırası (commit geçmişi, 16–17 Eylül 2026):**
1. İlk commit: yardımcı sinyal tasarım aracı (CVXPY), sonuçlar, plan, okuma listesi.
2. Sonra: dalga şekli üreteci ve ilk dedektör karşılaştırması (ML dahil).
3. Sonra: üç baralı hat içi / hat dışı modeli, gerçek EMT verisi, ML ile zone-1 kuralının adil
   karşılaştırması.
4. Sonra: bağımsız teknik inceleme (REVIEW.md) ve düzeltmeler.

**"Doğruluk alamadık" kısmı nereden geliyor olabilir?** İnceleme, ML'in ilk görünen üstünlüğünün
bir kısmının yapay olduğunu buldu:
- CV'de aynı simülasyonun kardeşleri hem eğitimde hem testte vardı (sızıntı);
- yeniden örnekleme arızayı 1 ms geriye sızdırıyordu;
- karşılaştırılan kural, standart röle özelliklerinden (yön elemanı, DC filtresi) yoksundu.

Bunlar düzeltilince ML hâlâ iyi ama "kuraldan açıkça üstün" iddiası daraldı. Bu, CVXPY'ye geçmenin
nedeni değil; CVXPY zaten projenin başından beri ana araçtı.

**Bugünkü durum, tek cümleyle:** CVXPY tasarım aracı iki baralı model içinde gerçek bir garanti
veriyor (ötesinde henüz değil). ML tarafında ise adapt_grid verisinde bir CNN, klasik tek uçlu
kuralın göremediği yüksek dirençli arızaların çoğunu sıfır yanlış açmayla yakalıyor: A rölesinde
açıkça, B rölesinde bölme kuralına bağlı olarak.

*Kaynak: `git log` (ilk commit 49541d4, "auxiliary-signal design toy"), `docs/PLAN.md` ("The
one-sentence version", WP1 ve WP3), `REVIEW.md` §1.*

---

## 2. CVXPY nedir, basitçe?

**CVXPY**, Python'da **optimizasyon problemi** çözmeye yarayan bir kütüphane. Optimizasyon, "kurallara
uyan seçenekler arasından en iyisini bul" demek.

**Nasıl çalışır:** CVXPY'ye üç şey yazılır:
1. **Değişken:** neyi seçeceğiz? Bizde enjekte edilecek sinyal δ.
2. **Amaç:** neyi en iyi yapmak istiyoruz? Bizde δ olabildiğince küçük olsun.
3. **Kısıtlar:** hangi kurallar sağlanmalı? Bizde her hat içi arıza her hat dışı arızadan ayrılsın,
   invertör akım limitini aşmasın.

CVXPY bunu standart bir forma çevirip bir çözücüye verir ve cevabı döndürür. Denklemi biz yazarız,
çözme işini o yapar.

**Benzetme:** navigasyon uygulaması. "Buradan şuraya git, paralı yol kullanma, en kısa yol olsun"
denir, o da rotayı bulur. CVXPY aynısını matematik problemleri için yapar.

**"Konveks" neden önemli:** CVX, konveks'ten gelir. Konveks problem çanak şeklindedir, tek bir dibi
vardır. Çözücü o dibi bulduğunda bunun **gerçekten en iyi cevap olduğunu kanıtlayabilir**: "daha iyisi
yok" ya da "bu kurallarla hiçbir çözüm yok" diyebilir. Taylor'ın yöntemine **garanti** dedirten budur.
ML modeli ise yalnızca "gördüğüm örneklerde işe yaradı" der, kanıt vermez.

**Projede ne yapıyor:** "Ölçüm hataları, yük durumu ve arıza direnci belirli aralıklarda ne olursa
olsun, röle hat içi ile hat dışı arızayı ayırt edebilsin. Bunun için gereken en küçük sinyal ne?"
sorusunu çözüyor.

**Dürüstlük notu:** problemin tamamı tam konveks değil. İlk yayımlanan çözümler bu yüzden "yerel" çıktı
(0.514 pu bulundu, gerçek en iyi değer 0.504 pu). İnceleme bunu global bir çözümle düzeltti, ayrıca
problemin δ'ya göre doğrusal bir parçası olduğunu gösterdi ve bununla ε = 0.16'da "hiçbir sinyal işe
yaramaz" sonucunu kesin olarak kanıtladı. Yani garanti mümkün, ama doğru kurulmuş bir problemle.

*Kaynak: `src/aux_model.py`, `src/aux_signal_toy.py` (tasarım aracı), `results/DESIGN.md` §2.1
(konvekslik sertifikası), `REVIEW.md` §1 madde 6 (0.514 → 0.504).*

---

## 3. CVXPY güç sistemlerine özgü bir şey mi?

**Hayır, genel amaçlı bir matematik aracı.** Stanford'da geliştirildi (Steven Diamond ve Stephen Boyd,
2016), açık kaynak ve ücretsiz.

**Başka alanlarda nerede kullanılıyor:**
- **Finans:** portföy optimizasyonu (riski sınırda tutarak getiriyi en yükseğe çıkaran dağılım).
- **Kontrol ve robotik:** model öngörülü kontrol (MPC), örneğin bir dronun ya da otonom aracın bir
  sonraki hareketi.
- **Makine öğrenmesi:** lasso regresyon, SVM gibi klasik modellerin eğitimi aslında konveks
  optimizasyon.
- **Sinyal işleme:** gürültülü sinyali temizlemek, eksik veriyi tamamlamak.
- **Lojistik:** kaynak dağıtımı, üretim planlama.
- **Güç sistemleri:** optimal güç akışı, üretim planlaması ve bizim projedeki yardımcı sinyal tasarımı.

**Güce özgü kısım bizim yazdığımız model.** Şebeke denklemlerini, arıza modellerini, ölçüm hatalarını
ve akım limitini biz tarif ediyoruz (`src/aux_model.py`); CVXPY problemi çözen motor. Benzetmeyle:
CVXPY hesap makinesi, formül bizim.

Bu yüzden projenin katkısı "CVXPY kullanmak" değil. Katkı, koruma problemini **doğru** bir optimizasyon
problemine çevirmek: doğru belirsizlik kümeleri, akım limiti problemin içinde, doğru hata modeli.
İncelemede bulunan hataların çoğu bu çeviri adımındaydı, CVXPY'de değil.

*Kaynak: Diamond & Boyd, "CVXPY: A Python-Embedded Modeling Language for Convex Optimization", JMLR
17(83), 2016; `src/aux_model.py`; `results/DESIGN.md` §5.*

---

## 4. Girdimiz ne, CVXPY'ye tam olarak ne soruyoruz?

**Soru:** "Hat içi arızada rölenin görebileceği ölçümler ile hat dışı arızada görebileceği ölçümler hiçbir
koşulda üst üste binmesin. Bunun için invertöre eklettirmem gereken **en küçük** sinyal ne?"

**Girdiler:**
1. **Şebeke modeli:** iki baralı basit şebeke. Röle L barasında, bir hat, karşıda R barası. Hat
   empedansları, uçlardaki kaynaklar (senkron generatör = gerilim kaynağı, invertör = akım kaynağı) ve
   yük tarif edilir (`src/aux_model.py`).
2. **Belirsizlik aralıkları:** kesin bilinmeyen şeyler ve ne kadar oynayabilecekleri:
   - generatör gerilimi: ±5 % büyüklük, ±5° açı;
   - invertör akımı: ±0.15 pu büyüklük, yaklaşık ±17° açı;
   - ölçüm hatası ε (eski modelde tek bir kutu; yeni modelde VT/CT kanalı başına ayrı hata);
   - invertör akım limiti (1.2 pu, ya da belirsiz kabul edilirse 1.1–2.1 pu).
3. **Ayırt edilecek durumlar:** arıza türü (faz-toprak, faz-faz), hattaki yeri (%15–%95) ve arıza
   direnci (0'dan en büyük değere). Bunlar iki grup oluşturur: "açılmalı" (hat içi arıza) ve
   "açılmamalı" (hat dışı arıza ya da normal çalışma).

Rölenin ölçtüğü şey: L barasındaki gerilim ve akımın pozitif, negatif ve sıfır bileşenleri (altı
kompleks sayı).

**Çıktı:**
- ya bir sinyal δ, yani bir büyüklük ve bir açı (örneğin "0.28 pu, şu açıyla");
- ya da kanıtlı bir "imkânsız": "bu aralıklarda hiçbir sinyal işe yaramaz" (ε = 0.16'daki sonuç).

**Benzetme:** her arıza durumu için rölenin görebileceği ölçümler bir **bulut** oluşturur; belirsizlik
yüzünden tek bir nokta değil, bir alandır. "Açılmalı" bulutlarıyla "açılmamalı" bulutları üst üste
biniyorsa röle ayıramaz. δ bu bulutları kaydırır. Sorulan: bulutları her durumda ayıran **en küçük
itme** ne?

**Neden "en küçük":** sinyal invertörün akım kapasitesinden yer ve şebekeyi rahatsız eder, gereğinden
büyük olmamalı.

*Kaynak: `src/aux_model.py` (`Params`, `solve`, `affine_model`, `separated_lp`),
`src/review/tac25_design.py` (akım limiti), `src/review/tac25_channels.py` (kanal başına hata).*

---

## 5. CVXPY'ye bir formül mü yazıyoruz? Kütüphane neyi nasıl seçiyor?

**Formül yazıyoruz, ama tek bir formül değil: bir problem tarifi.** Tasarım aracındaki gerçek kod
(`src/aux_signal_toy.py`), sadeleştirilmiş ve açıklamalı:

```python
d = cp.Variable(2)                                  # seçilecek şey: δ'nın iki sayısı (gerçel + sanal)
cons = [ayrilma_payi(ariza, d) >= gereken_pay       # kural: her arıza için bulutlar arası pay yeterli
        for ariza in arizalar]
prob = cp.Problem(cp.Minimize(cp.sum_squares(d)),   # amaç: |δ|² en küçük
                  cons)
prob.solve(solver=cp.CLARABEL)                      # çöz
```

Dört satır: **değişken, kurallar, amaç, çöz.** Nasıl seçileceğini biz söylemiyoruz; sadece neyin
istendiğini söylüyoruz.

**Kütüphane nasıl seçiyor:** tahmin etmiyor, rastgele denemiyor:
1. **Kontrol:** problemin konveks (çanak şeklinde) olup olmadığını kurallarla denetler. Değilse
   reddeder: "bunu garantili çözemem."
2. **Çeviri:** problemi çözücülerin anladığı standart matris formuna çevirir.
3. **Çözücü (CLARABEL):** izin verilen bölgenin içinden başlar, her adımda amacı biraz daha iyileştiren
   yöne kurallardan çıkmadan ilerler, daha fazla iyileşemeyince durur. Problem konveks olduğu için bu
   nokta kesinlikle en iyisidir. Çözücü bunun kanıtını da verir: "bundan iyisi yok" ya da "hiçbir
   çözüm yok".

**İnce nokta:** bizim tam problemimiz tek bir çanak değil. İçinde iki bilinmeyen çarpılıyor: sinyal δ
ve bulutların hangi yönden ayrılacağı (λ). Kod ikisini **sırayla** çözer: δ'yı sabitleyip en iyi yönü
bulur (konveks), yönü sabitleyip en küçük δ'yı bulur (konveks), tekrarlar. Her adım garantili, ama bu
sıralı yöntem en iyi sonuca varacağını garanti etmez. İlk yayımlanan 0.514 pu'nun gerçek en iyi değer
0.504 pu'dan kötü çıkması bu yüzdendir; inceleme global bir çözümle düzeltti.

*Kaynak: `src/aux_signal_toy.py` (Part 2, "Farkas-dual alternating optimization"), `REVIEW.md` H15.*

---

## 6. Gittiğimiz yön kötü mü, anlamsız bir şey mi yapıyoruz?

**Hayır, anlamsız değil.** Ama şu anki sonuçlar projenin **asıl sorusunu henüz cevaplamıyor**.

**Neden anlamlı:**
1. **Boşluk gerçek.** Sandia raporu (SAND2024-04848), grid-forming invertörlerin korumaya etkisi için
   sekiz koruma fonksiyonunun altısında "literatür bulunamadı" diyor. Yardımcı sinyal fikri ML
   literatüründeki ~600 referansın hiçbirinde geçmiyor. Taylor'ın yöntemi bu alanda **garanti** veren
   tek yöntem.
2. **Sağlam sonuçlar var:**
   - **Tasarım aracı** artık doğru kurulmuş: akım limiti problemin içinde, "imkânsız" sonucu kanıtlı.
   - **Yeni mekanizma:** IEEE 2800'e uyan bir invertör enjekte edilen sinyali 3–17 kat yutuyor. Bu,
     yöntemin pratikte çalışıp çalışmayacağını doğrudan etkiliyor ve hata modelinden bağımsız.
   - **ML'de gerçek bir niş:** tek uçlu klasik rölenin göremediği yüksek dirençli arızaları CNN iletişim
     olmadan, sıfır yanlış açmayla yakalıyor (A rölesinde açıkça).
   - **Değerlendirme protokolü:** veri sızıntısı, yanlış eşik noktası gibi tuzakları gösteren titiz bir
     yöntem; tek başına yayınlanabilir bir katkı.

**Neden henüz yeterli değil:**
1. **Asıl hedef test edilmedi.** Proje invertör ağırlıklı şebekeler hakkında, ama bütün gerçek veride
   invertörler kısa devre gücünün %0.14'ü. Hiçbir veri setinde enjekte edilmiş sinyal yok.
2. **Tasarım aracı yalnızca iki baralı modelde.** Taylor'ın 14 baralı örneği henüz tekrarlanmadı.
3. **İki bulgu yöntemin gerekliliğini sorgulatıyor:**
   - ölçüm hatası doğru modellenince (kanal başına) basit durumda **hiç sinyale gerek kalmıyor**;
   - standart invertörler sinyali yutuyor.

   Bunlar kötü haber değil, önemli bilgi; ama "sinyal şart" demeyi zorlaştırıyor.

**Öneri: yön doğru, odak daraltılmalı.**
1. Taylor'ın 14 baralı örneğini tekrarlamak (güvenilirlik için şart).
2. İnvertör ağırlıklı bir model bulmak: Taylor'ın kullandığı grid-forming invertörlü Simulink 14 baralı
   modeli (Baeckeland, Yang & Seo, IEEE TPWRS 2026) kendisinden istemek. Planın en başında da bu
   yazıyordu; asıl soruya ancak onunla cevap verilebilir.
3. Makalede yalnızca bugün kanıtlanabileni iddia etmek: değerlendirme protokolü, klasik röle
   karşılaştırması, doğru kurulmuş tasarım aracı, adapt_grid'deki niş. "Yardımcı sinyal invertörlü
   şebekede işe yarıyor" demek için henüz erken.

**Kısacası:** yanlış bir yola girmedik. Sağlam bir temel attık ve birkaç yanlış iddiayı erken yakaladık.
Asıl sorunun cevabı için bir sonraki adım, doğru şebeke modeline ulaşmak.

*Kaynak: `docs/PLAN.md` ("Why this is defensible", WP2), `REVIEW.md` §1 ve §10 madde 8,
`results/DESIGN.md` §4.1.1 ve §4.4, `results/ADAPTGRID.md` §4–5.*

---

## 7. Şu an çalışan koşuda neyi eğitiyor, neyi test ediyoruz? Kaç epoch?

Koşu: `src/review/rerun_cnn_deterministic.bat` (adapt_grid sonuçlarının deterministik yeniden üretimi).

**Görev:** röle, arıza anından sonraki 20 ms'lik gerilim ve akım ölçümüne bakıp "aç" ya da "açma" der.
- **"Aç" demesi gerekenler:** korunan hattın ilk %85'indeki arızalar (zone-1): A rölesinde 168, B'de 207.
- **"Açma" demesi gerekenler:** hattın dışındaki bütün kısa devreler: A'da 2.888, B'de 2.845.
- **Ayrıca test edilenler:** 5.474 anahtarlama olayı (arıza değil) ve 1.187 başlangıç halindeki arıza.

Veri: adapt_grid-TestGrid110kV, 9.739 EMT simülasyonu. Yük 2.8 kata kadar değişiyor, üç topraklama tipi
var, arıza direnci ve yeri sürekli değişiyor.

**Modeller:** altı dedektör aynı veride. T1 ve T2 klasik röle ayarı (eğitilmez, ayar seçilir);
engineered + LR, gradient boosting, CNN ve bir mesafe tahmincisi öğrenen modeller.

**CNN'in eğitimi (`src/review/q3_inputs.py`, `cnn_scores`):**
- **Girdi:** 24 kanal × 10 zaman adımı: gerilim ve akımın simetrili bileşenleri (V0, V1, V2, I0, I1, I2)
  ve arıza öncesine göre değişimleri, gerçel + sanal kısım, arızadan 2 ms'den 20 ms'ye kadar 2 ms'de bir.
- **Model:** iki evrişim katmanı (32 filtre, çekirdek 3), zamana göre ortalama, dropout 0.2, bir çıkış;
  toplam ~5.500 parametre.
- **Epoch: 40**, sabit, erken durdurma yok. Her epoch'ta ~2.000 eğitim örneği 32'lik gruplarla bir kez
  görülür (~60 adım); bir ağ toplam ~2.400 adım eğitilir.
- **Diğer ayarlar:** Adam, öğrenme hızı 0.002, weight decay 1e-4; hat içi arıza az olduğu için kaybı
  ~14–17 kat ağırlıklı (`pos_weight`: A rölesinde 2888/168, B rölesinde 2845/207).

**Kaç kez eğitiliyor:** veri iki şekilde bölünür: yük seviyesine göre 5 parça × 2 tekrar (10 fold) ve
yük çeyreğine göre 4 fold. Her fold için 5 ağ eğitilir (eşik ve test skoru bunlardan). Bir röle ve bir
front-end için yalnızca CNN'de ~140 eğitim; seed çalışması ve ters yön testiyle birlikte bütün koşuda
1.000'den fazla küçük CNN. Ağ küçük olduğu için her biri birkaç saniye.

**Test:** her fold'da model eğitimde **hiç görmediği** yük seviyelerindeki arızalarla test edilir. Eşik
"eğitimde hiçbir hat dışı arızada açmasın" noktasına kurulur. Ölçülenler:
- **bağımlılık:** hat içi arızaların yüzde kaçında açtı;
- **güvenlik:** hat dışı arızalarda kaç yanlış açma (örneğin 0/2888);
- **ek senaryolar:** ölçüm trafosu hatası farklıyken, başlama anı rölenin kendi tetiklemesinden
  alındığında ve başka bir röleye taşındığında sonuç.

*Kaynak: `src/review/adaptgrid_run.py` (modüller ve protokol), `src/review/q3_inputs.py`
(`seq_traj`, `cnn_scores`), `src/review/zone_cv.py` (`splits`), `results/ADAPTGRID.md` §3.*

---

## 8. Overfitting sorunumuz olmaz, değil mi?

**Olabilir, ama sonuçlarımızı yanıltmıyor.** Bu ikisini ayırmak önemli.

**Overfitting:** model eğitim örneklerini "ezberler"; gördüklerinde çok iyi, görmediklerinde daha kötü.

**Bizde biraz var.** 27 Eylül'deki tanı koşusunda tüm eğitim verisiyle eğitilen ağ, eğitimde gördüğü hat
dışı arızalara en fazla ~0–4 skor verirken görmediği arızalar için gereken eşik 5–20 arasındaydı: ağ
gördüğü örnekleri çok daha net ayırıyor. Bu bir ezber işareti; 40 sabit epoch ve erken durdurmanın
olmaması buna katkı veriyor.

**Neden sonuçları yanıltmıyor:** bütün sayılar modelin **hiç görmediği** veriyle ölçülüyor.
- Test verisi eğitimde de, eşik belirlemede de kullanılmıyor; kod bunu her koşuda kontrol ediyor
  (`adaptgrid_seeds.threshold_provenance`).
- Veri yük seviyesine göre bölünüyor; test edilen yük seviyesi eğitimde yok (loqo'da yükün bütün bir
  çeyreği dışarıda).
- Eşik, eğitim verisi ayrıca bölünerek "görülmemiş" skorlardan kuruluyor, ezberlenmiş skorlardan değil.
- Hiperparametreler test verisine bakılarak ayarlanmadı.

Ezber varsa bedeli raporlanan sayıların içinde. Model daha iyi yapılabilir, ama ölçüm dürüst.

**Asıl risk: tek bir şebekeye aşırı uyum (genelleme).** Bütün eğitim ve test aynı şebekede, aynı
topolojide, 50 Hz'de. İzleri:
- hiçbir dedektör bir röleden diğerine iki yönde birden taşınamıyor; her röle ayrı kalibrasyon istiyor;
- B rölesindeki sonuç bölme kuralına göre 45–84 % arasında oynuyor;
- farklı, özellikle invertör ağırlıklı bir şebekede sonuç bilinmiyor.

Makalede "bu şebeke için geçerli" diye açıkça yazılmalı.

**Eklenebilecek kontroller** (ölçümün dürüstlüğünü değiştirmez, modeli iyileştirebilir): eğitim ve
doğrulama kaybını epoch'a göre çizmek; iç fold'larda erken durdurma denemek.

*Kaynak: `src/review/q3_inputs.py` (`cnn_scores`: 40 epoch, dropout 0.2, weight decay 1e-4),
`src/review/adaptgrid_run.py` (`cnn_foldmean` ve eşik aktarımı ölçümü), `results/ADAPTGRID.md` §4–5.*

---

## 9. Eğitimde overfitting var mı, nasıl bakarız?

**Şu anki koşu bunu doğrudan göstermiyor.** Her ağ 40 epoch eğitiliyor ama epoch'lar boyunca kayıp
kaydedilmiyor; yalnızca sondaki test sonucu yazılıyor.

**Nasıl bakılır (öğrenme eğrisi):** bir fold'da ağı eğitirken **her epoch'ta** iki şey ölçülür:
- **eğitim kaybı:** ağın gördüğü örneklerdeki hatası;
- **doğrulama kaybı:** ağın hiç görmediği bir parçadaki hatası.

İkisi epoch'a göre çizilir:
- ikisi birlikte düşüyorsa model öğreniyor;
- eğitim kaybı düşmeye devam ederken doğrulama kaybı bir noktadan sonra **yükseliyorsa** ezber başlamıştır;
  o durumda 40 epoch fazladır ve erken durdurma gerekir.

**Şu an elimizdeki ipucu:** ağ gördüğü örnekleri görmediklerinden çok daha net ayırıyor, yani biraz ezber
var. Sonuçlar görülmemiş veriyle ölçüldüğü için sayılar yine dürüst (bkz. soru 8).

**Plan:** A ve B rölesinde birkaç fold için epoch başına eğitim ve doğrulama kaybını çizen küçük bir betik
(~10–15 dakika). Büyük koşu bitince çalıştırılacak; aynı anda koşarsa RAM ve GPU'yu paylaşırlar.

**Sonuç (27 Eylül 2026, `src/review/cnn_learning_curve.py`):** A ve B rölesinde 3'er fold, 120 epoch. Betikteki
ağ 40. epoch'ta yayımlanan ağla bit düzeyinde aynı (6 fold'un hepsinde).
- **Klasik overfitting yok:** görülmemiş yük seviyelerindeki kayıp eğitim kaybıyla birlikte düşüyor; en
  düşük noktası 71–120. epoch'ta. 40 epoch fazla değil.
- **Asıl sorun kararsız eğitim:** kayıp birkaç epoch'ta bir 10–1000 kat sıçrıyor (hem eğitimde hem testte);
  muhtemel neden öğrenme hızı 0.002 + küçük grup (32) + 14–17 kat sınıf ağırlığı. 40. epoch'taki ağın bir
  sıçramanın içinde olup olmaması şansa bağlı.
- **B'de hafif genelleme farkı:** eğitim kaybı ~1e-4'e inerken görülmemiş veride ~1e-2'de kalıyor (ama
  yükselmiyor); eşik aktarım farkı epoch'tan epoch'a ±10 oynuyor.
- **Anlamı:** B'deki kararsızlığın kaynağı ezber değil, kararsız eğitim ile tek bir en yüksek skora bağlı
  eşiğin birleşimi. İyileştirme (yeni deney, seçim iç fold'larla): daha düşük / azalan öğrenme hızı,
  gradyan kırpma, son epoch'ların ağırlık ortalaması.

*Kaynak: `results/adaptgrid/learning_curve_relayfe_cnn.json` ve `.png`.*

---

## 10. Veri setimizde neler var?

Veri **EvEMTBench**'ten (FAU Erlangen): gerçekçi elektromanyetik geçici rejim (EMT) simülasyonları, yani
rölenin göreceği gerilim ve akım dalga şekilleri. Üç parçası kullanıldı:

| | DoubleLine (benchmark) | TestGrid110kV (benchmark) | **adapt_grid** (şu an kullanılan) |
|---|---|---|---|
| Simülasyon | 1.101 | 2.435 | **9.739** |
| Yük durumu | tek | tek, sabit | **değişken, 210–596 MW (2.8 kat)** |
| Topraklama | tek | tek | **3 tip: rezonans, dirençli, solid** |
| Arıza yeri | %1 / 20 / 50 / 80 / 99 | %1 / 20 / 50 / 80 / 99 | **sürekli, %1–99** |
| Arıza direnci | 1 / 10 / 40 Ω | 1 / 10 / 40 Ω | **sürekli, 0.03–50 Ω (medyan 25 Ω)** |
| Anahtarlama olayı | 24 | 50 | **5.474** |
| Başlama anı | sabit | sabit | **rastgele, dalganın her noktası** |

**adapt_grid'in içeriği** (110 kV, 50 Hz):
- **Kısa devreler:** faz-toprak, faz-faz, faz-faz-toprak, üç faz; şebekenin farklı hat ve baralarında.
- **Anahtarlama olayları:** 5.474 adet, 9 türde. Arıza değiller, röle açmamalı.
- **Başlangıç halindeki (incipient) arızalar:** 1.187 adet.
- **İki röle:** A (MainLn1-2A) ve B (MainLn2-3):
  - hat içi (açmalı): A'da 168, B'de 207 (yalnızca hattın ilk %85'i sayıldığı için az);
  - hat dışı (açmamalı): A'da 2.888, B'de 2.845; alt gruplar: karşı bara, sonraki hat, paralel hat,
    rölenin arkası, diğer.
- **Her simülasyonda:** rölenin gördüğü 3 faz gerilim ve 3 faz akım, saniyede 6.400 örnek, arızadan önce
  ve sonra 100 ms.
- **Etiketler:** arıza türü, yeri, direnci, topraklama, yük seviyesi.

**Güçlü yanları:**
- güvenlik ilk kez sıkı ölçülebiliyor (binlerce hat dışı arıza ve anahtarlama olayı);
- benchmark'taki sızıntı yok: her simülasyon benzersiz, arıza öncesinden sonuç tahmin edilemiyor
  (AUC 0.52).

**Zayıf yanları:**
- **kaynak gücü değişmiyor:** şebeke hep güçlü (SIR ≤ 1.4), zayıf şebeke test edilemiyor;
- **invertörler çok küçük:** kısa devre gücünün %0.14'ü; invertör ağırlıklı şebeke yok;
- **tek topoloji**, yalnızca 50 Hz;
- **ölçüm trafoları ideal**; CT/CVT hataları sonradan modelle ekleniyor;
- **enjekte edilmiş yardımcı sinyal hiçbir simülasyonda yok.**

*Kaynak: `results/ADAPTGRID_FACTS.md`, `results/ADAPTGRID.md` §1–2 ve §5, `results/DATASET_FACTS.md`.*

---

## 11. Train / validation / test düzgün ayrılmış mı?

**Evet.** Kod bunu her koşuda kontrol ediyor; yayımlanan sonuçlarda örtüşme **sıfır**.

**Üç katman:**
1. **Test ↔ eğitim (dış bölme):** veri yük seviyesine göre 20 gruba ayrılır.
   - **grouped:** 5 parça, her seferinde ~4 yük grubu tamamen teste; iki tekrar.
   - **loqo:** yükün bütün bir çeyreği teste; model o yük aralığını hiç görmez. En zor test.
2. **Eğitim ↔ doğrulama (iç bölme, eşik için):** eğitim kısmı yine yük grubuna göre 5'e bölünür. Eşik
   "hiçbir hat dışı arızada açma" noktasına, ağların **görmediği** doğrulama skorlarından kurulur.
3. **Test hiçbir şeye dokunmaz:** eğitimde, eşikte, hiperparametre seçiminde kullanılmaz; en sonda bir
   kez ölçülür.

**Kod kontrolü:** `threshold_provenance` gerçek indeks kümelerine bakar. Yayımlanan sonuçta eşiği
belirleyen satırlardan teste düşen **0**, eşiği belirleyen yük gruplarından teste düşen **0**; iki bölme
şeklinde de.

**Ek güvenceler:**
- adapt_grid'de her simülasyon benzersiz; kopya ya da "kardeş" simülasyon yok (benchmark'taki H22
  sızıntısı burada yok).
- Normalizasyon (CNN kanal ortalama/sapması, LR ölçekleyicisi) yalnızca eğitim verisinden hesaplanır.
- Arıza öncesi pencereden sonuç tahmin edilemiyor (AUC 0.52): gizli kısayol yok.

**Bilinmesi gereken sınırlar (hata değil):**
1. **roc0 / roc1'de eşik test verisinden okunur.** Bilerek "üst sınır" diye raporlanır; gerçekçi sonuç
   **cal0**.
2. **Anahtarlama ve başlangıç arızaları eğitimde hiç yok**, yalnızca test edilir. Ama fold modellerinin
   çoğunluk oyuyla skorlanırlar ve o modellerin çoğu olayın yük seviyesini eğitimde görmüş olabilir; bu
   olaylar için yük ayrımı tam değildir.
3. **grouped'da komşu yük grupları eğitimde kalabilir** (5. grup testte, 4. ve 6. eğitimde); bu yüzden
   grouped nispeten kolay. Gerçek genelleme testi **loqo**.
4. **Ters yön arızaları eğitimdeydi;** 27 Eylül'de held-out olarak ayrıca test edildi.

*Kaynak: `src/review/zone_cv.py` (`splits`), `src/review/common.py` (`grouped_folds`),
`src/review/adaptgrid_seeds.py` (`threshold_provenance`), `results/adaptgrid/seeds_adapt_A_relayfe_cnn.json`,
`results/ADAPTGRID_FACTS.md`.*

---

## 12. Bizim için en uygun veri seti hangisi? Benzer çalışmalar hangi veriyi kullanmış?

**Benzer çalışmalar:** neredeyse hepsi kendi simülasyonunu kurmuş (PSCAD ya da Simulink); hazır bir kamu
veri seti kullanan yok denecek kadar az (okuduğumuz yapay zekâ taraması da bunu yazıyor).

| Çalışma | Veri |
|---|---|
| Taylor 2023 (yöntemin kendisi) | Tek hatlı basit model, statik |
| Taylor 2025 (TAC) | IEEE 14 baralı sistem, statik model |
| Taylor 2026 (erişilebilirlik) | Simulink IEEE 14 baralı model, 5 grid-forming invertör (Baeckeland, Yang & Seo 2026); kamuya açık değil |
| Artımlı negatif sekans yöntemi (rakip) | MATLAB/Simulink topluluk mikro şebekesi |
| Artımlı büyüklük mesafe koruması, GFM ile (rakip) | PSCAD, 220 kV 100 km hat; donanım testi (CHIL) |
| ML ile %100 invertörlü mikro şebeke koruması | PSCAD, 4 baralı mikro şebeke, 420 simülasyon |
| **Hasan, Chakraborty & Wang 2026** (bize en benzeri) | PSCAD'de kendi ürettikleri binlerce EMT simülasyonu, invertör ağırlıklı zayıf şebeke; iletişimsiz, tek uçlu, zone sınıflandırma, SVM; 2.5 çevrimde %97.2 doğruluk |
| FAU grubu (Oelhaf, Kordowich, Jäger) | PROTECT-90 ve EvEMTBench (bizim kullandığımız) |

**Dikkat edilecek iki yeni çalışma:**
1. **Hasan ve ark. 2026** bizim ML nişimizle neredeyse aynı fikir (tek uçlu, iletişimsiz, invertörlü
   şebekede zone kararı). Makalede karşılaştırılmalı. Onlar "%97.2 doğruluk", biz "sıfır yanlış açmada
   bağımlılık" raporluyoruz; bizimki koruma açısından daha sıkı bir ölçüt.
2. **FAU grubunun Ağustos 2026 makalesi** ("A Standardized Framework for Machine Learning in Power System
   Protection") ML koruma çalışmalarının değerlendirilmesi için standart bir çerçeve öneriyor; bizim
   "değerlendirme protokolü" katkımızla örtüşüyor. Atıf yapılıp farkımız gösterilmeli.

**Bizim için en uygun veri:**
1. **Hemen yapılabilir: EvEMTBench adapt_grid CigreMV 20 kV.** Kaynak olarak yalnızca invertör bağlı
   (baraların ~%20'si). "İnvertör ağırlıklı" eksiğimize en yakın hazır veri. Aynı aile ve format, mevcut
   kod neredeyse değişmeden çalışır; lisans gerekmez (~35 GB indirme, bir kerelik önbellek). **Dikkat:**
   şebeke 110 kV'tan trafoyla besleniyor; arıza akımında invertör payı önce ölçülmeli (110 kV'ta %0.14
   çıkmıştı). 20 kV'ta mesafe koruması 110 kV'taki kadar tipik değil.
2. **"Tek şebeke" zayıflığı için: EvEMTBench multigrid 110 kV.** 105 rastgele topoloji; modelin tek
   şebekeyi ezberleyip ezberlemediğini test etmenin en iyi yolu.
3. **Asıl soru (yardımcı sinyal) için değiştirilebilir bir model gerekli;** hiçbir hazır veride
   enjekte edilmiş sinyal yok:
   - **Taylor'dan Baeckeland 14 baralı Simulink modelini istemek** (en iyi seçenek: Taylor'ın kendi
     modeli, grid-forming, akım sınırlayıcısı açık; planda ilk adımdı);
   - **IRTSD (PNNL):** 6 bara, 230/500 kV, %40 invertör, 60 Hz, PSCAD modeli açık; sinyal eklemek
     dokümanda tarif edilmiş. PSCAD Educational lisansı gerekir, her değişiklikte model yeniden
     oturtulmalı;
   - **PNNL T&D test sistemi:** GFL + GFM, IEEE 2800, CCVT modeli; ama GFM kara kutu ve muhtemelen PSCAD
     Professional gerekir.
4. **Yardımcı: PROTECT-90.** İnvertör yok; ölçüm ön işlemesini doğrulamak için iyi.

**Önerilen sıra:** (1) CigreMV 20 kV ile mevcut analizi tekrarlamak (birkaç gün, lisanssız); (2) paralel
olarak Taylor'dan 14 baralı modeli istemek.

*Kaynak: `papers/notes/D_ml_and_datasets.md` (§12–20, PSCAD lisansı), `papers/notes/A_taylor_line.md`,
`papers/notes/C_competing_methods.md`, `papers/notes/F_taylor_tac_and_gfm_model.md`; Hasan, Chakraborty &
Wang, IJEPES 181 (2026) 112007; Oelhaf ve ark., arXiv:2608.20181 (2026).*

---

## 13. Hasan ve ark. (2026) ile FAU çerçevesi (2026) hangi yöntemleri kullanıyor? Bizimle aynı mı, daha mı iyi?

**Kısa cevap:** biri aynı problemi farklı yöntemle çözüyor, öteki bizimkine benzer bir değerlendirme
çerçevesi öneriyor. Hiçbiri toptan daha iyi değil; ikisinin de bizde olmayan güçlü yanları var.

### Hasan, Chakraborty & Wang 2026 (NREL), IJEPES 181, 112007

**Ne yapmışlar:**
- **Şebeke:** gerçek bir 60 Hz şebekenin iki baralı eşdeğeri, 57 kV hat. Bir uçta güçlü generatör
  şebekesi, **rölenin olduğu uçta 14 MVA grid-forming batarya invertörü** (üretici kara kutu modeli).
- **Veri:** PSCAD'de 2.970 simülasyon; 11 arıza tipi, 26 sabit konum (8'i ters yön), 11 sabit arıza
  direnci **yalnızca 0–10 Ω**, 3 yük durumu.
- **Yöntem:** 4 aşamalı **doğrusal SVM** (arıza var mı + yön; tip; zone 1/2; konum), her aşama için elle
  tasarlanmış öznitelikler (simetrili bileşenler vb.), 3 çevrimlik pencere.
- **Bölme:** rastgele %70 eğitim / %30 test.
- **Sonuç:** "%97.2 genel doğruluk". Tespit, yön, tip %100; **zone kararı faz-faz arızalarda %78, üç
  fazlıda %88**; karar 2–2.5 çevrimde.
- **Güvenlik testi:** gerilim çökmesi, generatör kaybı, invertör güç değişimi (birkaç senaryo); çok derin
  bir gerilim çökmesinde 1 yanlış açma.

**Bizden iyi oldukları yerler:**
1. **Fizik:** röle ucunda gerçekten grid-forming invertör var (bizde invertör payı %0.14); bizim en büyük
   eksiğimiz onlarda var.
2. **Uçtan uca test:** röle modeli simülasyonun içinde (co-simulation), karar süresi ölçülmüş.
3. **Tam röle:** yön, tip, zone ve konum birlikte; doğrusal SVM basit, yorumlanabilir, donanıma kolay.
4. **60 Hz.**

**Bizim güçlü olduğumuz yerler:**
1. **Değerlendirme sıkılığı:** "%97.2" dört aşamanın doğruluk **ortalaması**; kolay aşamalar (%100) zor
   aşamayı (zone, %78) gizliyor. Biz **sıfır yanlış açma eşiğinde bağımlılık** ölçüyoruz, binlerce hat
   dışı arızada güven sınırlarıyla.
2. **Sızıntı riski:** rastgele 70/30 bölme ve sabit bir konum/direnç ızgarası; test örneğinin komşusu
   büyük ihtimalle eğitimde. Kendi benchmark'ımızda bu sorunu (H22) bulup düzelttik; FAU çerçevesi de
   bunu açıkça yasaklıyor.
3. **Veri çeşitliliği:** 9.739 simülasyon (onlarda 2.970); sürekli değişen yük (onlarda 3 durum); 3
   topraklama tipi (onlarda solid); rastgele arıza anı; 5.474 anahtarlama olayıyla güvenlik testi
   (onlarda anahtarlama, kondansatör, inrush yok).
4. **Yüksek arıza direnci:** onlar "10 Ω üstü tek uçlu ölçümle yapılamaz, iletişim gerekir" diyor ve 10
   Ω'da kesiyor. Bizim nişimiz tam orası (medyan 22–24 Ω, klasik rölenin göremediği arızalar, iletişimsiz,
   sıfır yanlış açma). **Ama adil olmak gerekirse:** bizim şebeke güçlü ve generatör ağırlıklı, onlarınki
   röle ucunda zayıf ve invertörlü; bizim yüksek direnç sonucumuz onların şebekesinde tutmayabilir. İki
   iddia aynı fiziği test etmiyor.
5. **Klasik röleyle karşılaştırma:** biz aynı veride ayarlanabilir klasik rölelerle karşılaştırıyoruz
   (R2, T1/T2, 67N/67Q, iki uçlu 32P/32Q); onlarda aynı veride klasik röle sonucu görmedim.

**Sonuç:** fizik tarafında onlar, değerlendirme ve veri tarafında biz öndeyiz. Makale konumu: "benzer tek
uçlu fikir; biz protection-grade eşikte, çok daha büyük ve çeşitli veride, sızıntısız ve güven
sınırlarıyla ölçüyoruz; eksiğimiz invertör ağırlıklı fizik."

### Oelhaf ve ark. 2026 (FAU), "A Standardized Framework for Machine Learning in Power System Protection", arXiv:2608.20181

**Ne öneriyorlar:** ML koruma çalışmalarında raporlanması gereken 7 boyut: görev tanımı, fiziksel kapsam,
ölçümler, zamanlama/pencere, etiketleme, eğitim/doğrulama protokolü, çıktılar. PROTECT-90 üzerinde
(invertörsüz 90 kV hat) gösteriyorlar; sınıflandırma ve konum tahmini yapıyorlar, zone/trip kararı değil.

**Bizimle ortak:** simülasyon bazında gruplanmış bölme; ön işlemenin yalnızca eğitim verisinden
hesaplanması; hiperparametrelerin teste bakmadan seçilmesi; klasik yöntemle karşılaştırma; ölçüm
bozulmasına dayanıklılık; belirsizliğin kaynağını raporlamak (fold, seed).

**Onlarda olup bizde eksik:** gerçek donanımda karar süresi (latency) ölçümü; "hangi ölçümler varsa sonuç
ne olur" analizinin sistematik yapılması.

**Bizde olup onlarda olmayan** (onların "gelecek çalışma" dediği): hat dışı arızalarda sınıf bazlı
güvenlik ölçümü ve binom güven sınırları; sıfır yanlış açma eşiği ve fold dışı kalibrasyon; ters yön
arızaları ve yön elemanı; kopya/kardeş simülasyonların ayıklanması; invertörlü şebeke.

**Sonuç:** tamamlayıcı. Ama "değerlendirme protokolü bizim katkımız" iddiasının genel kısmını bu makale
kapsıyor. İddia daraltılmalı: bizim katkımız çerçevenin **korumaya özgü güvenlik kısmı** (sıfır yanlış
açma eşiği, hat dışı ve ters yön arızalarında sınıf bazlı güvenlik, fold dışı eşik). Onlara atıf yapıp
"onların gelecek çalışma dediği şeyi yaptık" diye konumlamak hem dürüst hem güçlü.

*Kaynak: Hasan, Chakraborty & Wang, "End-To-End Decentralized Transmission Line Protection in
IBR-Dominated Weak Grids Using Interpretable Data-Driven Methods", IJEPES 181 (2026) 112007 (OSTI
3577322), §3.1–3.2, §5.4, §7; Oelhaf ve ark., arXiv:2608.20181 (2026).*

---

## 14. Baktığımız makalelerin veri setleri açık kaynak mı?

**Çoğu değil.** Açık olanlar yalnızca veri seti yayınlamak için yapılmış çalışmalar; yöntem makalelerinin
hiçbiri verisini paylaşmamış.

**Açık olanlar:**

| Kaynak | Ne paylaşılmış | Lisans |
|---|---|---|
| **EvEMTBench** (bizim kullandığımız) | Bütün veri (11 dosya, ~615 GB) | İndirilebilir, ama **lisans belirtilmemiş, DOI yok**: kullanıp atıf yapabiliriz, verinin kendisini dağıtmamalıyız |
| **PROTECT-90** | Bütün veri, 9.022 simülasyon | **CC BY 4.0** (Zenodo) |
| **IRTSD** (PNNL) | Veri (5.500 olay, 30 GB) + PSCAD modeli + otomasyon betikleri | **CC BY 4.0** |
| **PNNL T&D test sistemi** | PSCAD modeli + 3 örnek (olay verisi yok) | Açık erişim; GFM invertörü kara kutu |

**Açık olmayanlar:**

| Çalışma | Durum |
|---|---|
| **Hasan ve ark. 2026** (bize en benzeri) | Makalede: *"The data that has been used is confidential."* Gerçek şebeke ve üretici invertör modeli; gizli |
| **Taylor 2023 / 2025** | Veri gerekmiyor: örnekler makalede bütün sayılarıyla verilmiş, yeniden kurulabilir; kod paylaşılmamış |
| **Taylor 2026 (Baeckeland 14 baralı Simulink modeli)** | Şebeke verisi standart IEEE 14 bara (açık); **invertör modelleri yazarlarda**, istenmesi gerekiyor |
| **Beikbabaei 2024** (ML, %100 invertörlü mikro şebeke) | Veri, model ya da kod paylaşımı yok |
| **Johansson ve ark. 2026** (artımlı büyüklük mesafe koruması + GFM) | Paylaşım yok (PSCAD'de yüzlerce koşu, yayınlanmamış) |
| **Georgia Tech gecikme çalışması** | Hiçbir şey paylaşılmamış; ticari simülatör |
| **FAU karşılaştırma ve çerçeve makaleleri** | Kendi verileri yok; PROTECT-90 kullanıyorlar (açık) |

**Bizim için anlamı:**
1. **Tekrarlanabilirlik avantajımız.** En benzer çalışma (Hasan) gizli veri kullanıyor, sonucu kontrol
   edilemez. Biz herkesin indirebildiği veri ve açık kodla çalışıyoruz; makalede vurgulanmalı.
2. **Hasan'ın sonucu tekrarlanamaz, ama yöntemi bizim veriye uygulanabilir.** Doğrusal SVM ve aşamalı yapı
   kolay kurulur; aynı veride iki yöntemi karşılaştırmak adil ve güçlü olur.
3. **EvEMTBench lisans belirsizliği:** kodumuzu ve sonuç dosyalarımızı paylaşabiliriz, ham veriyi repoya
   koymamalıyız (koymuyoruz); makalede indirme bağlantısı yeterli.
4. **İnvertör ağırlıklı ve sinyal enjekte edilebilir açık tek seçenek IRTSD** (PSCAD lisansı gerekir);
   Taylor'ın modeli ancak isteyerek alınabilir.

*Kaynak: `papers/notes/D_ml_and_datasets.md` (karşılaştırma tablosu, §15–20), `papers/notes/F_taylor_tac_and_gfm_model.md`
(BYS26), Hasan ve ark. 2026 "Data availability" bölümü; Beikbabaei ve ark. (arXiv:2405.07310) ve
Johansson ve ark. (arXiv:2604.10129) metinlerinde paylaşım ifadesi bulunmadı.*

---

## 15. Onlardaki güçlü yanları kendimize ders olarak alamaz mıyız?

**Alabiliriz; çoğu zor değil.**

**Hızlı kazanımlar (birkaç saat):**
1. **Hasan'ın yöntemini bizim veride denemek:** kendi özniteliklerimizle doğrusal SVM'i ekstra model olarak
   eklemek. Gizli verili bir çalışmayla aynı veride adil karşılaştırma.
2. **Karar süresini ölçmek (FAU):** CNN'in bir kararı kaç mikrosaniyede verdiği (CPU). "Gerçek zamanlı
   rölede çalışır mı?" sorusuna sayıyla cevap; ağ küçük olduğu için büyük ihtimalle bizim lehimize.
3. **Makaleyi FAU'nun 7 boyutuna göre yapılandırmak:** yazım işi; standarda uyduğumuzu gösterir.

**Orta vadeli (birkaç gün):**
4. **Gerçek röle gibi sürekli karar (Hasan):** şu an tek bir pencere (arızadan 20 ms sonra) veriliyor;
   gerçek röle her an karar verir. Kayıt boyunca pencereyi kaydırıp modelin **ilk ne zaman açtığını** ve
   arıza öncesinde yanlışlıkla açıp açmadığını ölçmek. Hasan'ın uçtan uca testine en yakın şey, PSCAD
   gerektirmeden. En değerli madde.
5. **Karar süresi taraması:** 10, 15, 20, 30, 40 ms. "Ne kadar beklersek ne kadar kazanırız" eğrisi;
   Hasan 2–2.5 çevrim (33–42 ms), biz 1 çevrim (20 ms). Aynı eksende karşılaştırma.
6. **Eksik ölçümle performans (FAU):** yalnızca akım, yalnızca gerilim, sıfır bileşensiz. Modelin neye
   dayandığını gösterir; Hasan'ın gözlemi (invertörlü şebekede negatif bileşen akımı invertör kontrolüne
   bağlı, güvenilmez) burada işe yarar.
7. **Ölçüm bozulmasına dayanıklılık (FAU):** gürültü seviyesi, CT doyması; sistematik tarama. FAU'nun
   bulgusu "temiz veride en iyi model bozuk veride en iyi olmayabilir"i kendi modellerimizde test eder.

**Uzun vadeli (asıl eksik):**
8. **Röle ucunda gerçek invertör (Hasan'ın en güçlü yanı):** veri gerekiyor; plan CigreMV 20 kV, sonra
   Taylor'ın modeli ya da IRTSD.
9. **Fiziksel açıklama (Hasan'dan yazım dersi):** onlar "neden 10 Ω'da kestik"i fizikle açıklıyor. Biz de
   "yüksek dirençli arızayı neden yakalayabiliyoruz"u açıklamalıyız (büyük ihtimalle güçlü generatör
   kaynağı); sonucun nerede geçerli olup nerede olmadığını dürüstçe gösterir.

**Önerilen sıra (eğitim bittikten sonra):** öğrenme eğrisi → madde 1 ve 2 → madde 4.

*Kaynak: Hasan ve ark. 2026 (§3.2, §4, §7); Oelhaf ve ark. 2026 (arXiv:2608.20181); bu dosyanın 12–14. soruları.*

---

## 16. Şu anki eğitimde veri setinde hangi tür veriler var, nasıl bölünmüş?

### Olay türleri (toplam 9.739 simülasyon)

| Tür | Adet | Açıklama |
|---|---|---|
| **Kısa devreler** | 3.078 | Şebekenin her yerinde; faz-toprak, faz-faz, faz-faz-toprak, üç faz |
| **Anahtarlama olayları** | 5.474 | Arıza değil: yük, kondansatör, hat açma/kapama, trafo enerjilendirme vb. 9 tür |
| **Başlangıç (incipient) arızalar** | 1.187 | Çok kısa süren, kendiliğinden sönen arızalar |

### Bir röle açısından sınıflar

| Sınıf | A | B | Röle ne yapmalı | Eğitimde mi? |
|---|---|---|---|---|
| **Hat içi arıza** (kendi hattının ilk %85'i) | 168 | 207 | **Açmalı** | Evet |
| **Koruma bandı** (kendi hattının %85–100'ü) | 22 | 26 | İkisi de kabul | Hayır (ayrı raporlanır) |
| **Hat dışı arızalar**, toplam | 2.888 | 2.845 | **Açmamalı** | Evet |
| ↳ karşı barada | 184 | 207 | | |
| ↳ sonraki hatlarda | 645 | 223 | | |
| ↳ paralel hatta | 214 | 0 | | |
| ↳ rölenin kendi barasında (ters yön) | 188 | 184 | | |
| ↳ rölenin arkasındaki hatlarda (ters yön) | 199 | 816 | | |
| ↳ şebekenin başka yerlerinde | 1.458 | 1.415 | | |
| **Anahtarlama olayları** | 5.474 | 5.474 | Açmamalı | **Hayır**, yalnızca test |
| **Başlangıç arızaları** | 1.187 | 1.187 | Raporlanır | **Hayır**, yalnızca test |

**Dengesizlik:** açması gereken örnek çok az (A'da 168'e karşı 2.888, ~1'e 17); kayıptaki ~14–17 katlık
ağırlık bu yüzden.

**Hat içi arızaların arıza direncine göre dağılımı:**

| Arıza direnci | ≤ 1 Ω | 1–10 Ω | 10–40 Ω | > 40 Ω |
|---|---|---|---|---|
| A | 3 | 25 | 114 | 26 |
| B | 5 | 46 | 119 | 37 |

Çoğu yüksek dirençli: klasik rölenin zorlandığı, CNN'in fark yarattığı yer. Topraklama her röle için
yaklaşık üçte bir solid, dirençli, rezonans.

### Bölme

**Yük seviyesine göre:** 9.739 simülasyon toplam yüke göre sıralanıp 20 eşit gruba (~487) ayrılır. Bir grup
ya tamamen eğitimde ya tamamen testte.

| | **grouped** | **loqo** |
|---|---|---|
| Test | Her seferinde ~4 yük grubu (%20) | Bir yük çeyreği = 5 komşu grup (%25) |
| Eğitim | Kalan %80 | Kalan %75 |
| Tekrar | 5 parça × 2 tekrar = 10 fold | 4 fold |
| Zorluk | Daha kolay (komşu yükler eğitimde olabilir) | Daha zor (o yük aralığı hiç görülmemiş) |

Örnek (A, grouped, bir fold): eğitimde ~134 hat içi ve ~2.310 hat dışı arıza; testte ~34 hat içi ve ~578
hat dışı.

**Eğitimin içinde ikinci bölme (eşik için):** eğitim verisi yine yük grubuna göre 5'e bölünür, 5 ağ
eğitilir. Eşik, ağların görmediği parçadaki skorlardan "hiçbir hat dışı arızada açma" noktasına kurulur;
test verisini bu 5 ağın ortalaması skorlar.

**Anahtarlama ve başlangıç arızaları eğitimde hiç yok:** her fold modeli onları skorlar; fold modellerinin
yarısından fazlası "aç" derse yanlış açma sayılır.

*Kaynak: `results/ADAPTGRID_FACTS.md` (sınıf tabloları, R_f ve topraklama dağılımı),
`src/review/common.py` (`load_relay_adapt`: sınıf tanımları, 20 yük grubu),
`src/review/zone_cv.py` (`zone_task`, `splits`), `src/review/adaptgrid_run.py` (`cnn_foldmean`).*

---

## 17. Veri bu kadar dengesiz olunca kötü bir öğrenme olmaz mı?

**Dikkat edilmesi gereken bir şey, ama bizde kötü öğrenmeye yol açmıyor; önlemi alınmış.** Asıl yan etkisi
ölçümün hassasiyetinde.

**Dengesizlik ne zaman kötü öğrenmeye yol açar:** 1'e 17 oranında hiç "aç" demeyen bir model bile %94 doğru
görünür; model hep çoğunluk sınıfını söylemeyi öğrenebilir, "doğruluk" bunu gizler.

**Bizde neden olmuyor, dört önlem:**
1. **Kayıp ağırlıklı:** CNN'de bir hat içi arızayı kaçırmak ~14–17 kat pahalı (`pos_weight`); LR'de
   `class_weight="balanced"`; gradient boosting'de azınlık sınıfı çoğaltılıyor (`real_ml.fit_balanced`).
2. **"Doğruluk" kullanılmıyor:** bağımlılık (hat içi) ve yanlış açma sayısı (hat dışı) **ayrı ayrı**
   ölçülüyor; hep "açma" diyen model %0 bağımlılık alır, gizlenemez (Hasan'ın "%97.2 doğruluk"undan bu
   yüzden daha sağlam).
3. **Eşiği biz koyuyoruz:** sınıf oranına göre değil, "hiçbir hat dışı arızada açma" kuralına göre.
4. **Dengesizlik gerçeği yansıtıyor:** gerçek röle de kendi hattındaki arızadan çok daha fazla dış olay
   görür; güvenliği ağır basan bir test doğru bir test.

**Asıl yan etki: az örnek, hassas olmayan ölçüm:**
1. **Bağımlılık tahmini belirsiz:** A'da 168 hat içi arıza, grouped'ın bir fold'unda testte ~34; her
   kaçırılan arıza ~3 puan. B'de sonucun bölme kuralına göre 45–84 % arasında oynamasının bir nedeni.
2. **Alt gruplarda iddia kurulamaz:** 1 Ω altında A'da 3, B'de 5 hat içi arıza.
3. **Öğrenilecek çeşitlilik sınırlı:** 134 eğitim örneği az; bu yüzden çok küçük bir ağ (~5.500
   parametre) kullanılıyor, büyük model ezberlerdi.

**Ne yapılabilir:**
- **Hat dışı örnekleri azaltmak (undersampling): yapılmamalı**, güvenlik kanıtını azaltır.
- **Yapay örnek üretmek (augmentation): riskli**, fiziksel olarak tutarsız dalga şekli üretebilir.
- **Daha fazla gerçek hat içi arıza: doğru yol.** Daha büyük veri (CigreMV'de daha çok hat ve röle) ya da
  aynı şebekenin başka hatlarını röle olarak eklemek (önbellekte 3 hat ucu daha var).
- **Güven aralığıyla raporlamak:** yapılıyor (bağımlılık için gruplanmış bootstrap, yanlış açma için binom
  üst sınırı).

**Kısacası:** dengesizlik öğrenmeyi bozmuyor; az sayıdaki hat içi arıza sonuçları gürültülü yapıyor. Bu
daha fazla veriyle çözülecek bir sorun.

*Kaynak: `src/review/q3_inputs.py` (`cnn_scores`, `pos_weight`), `src/real_ml.py` (`models`,
`fit_balanced`), `src/review/adaptgrid_run.py` (`rates_plus`: bootstrap ve binom sınırları),
`results/ADAPTGRID_FACTS.md`, `results/ADAPTGRID.md` §4.*

---

## 18. Deney istediğimiz sonuçları verdi mi? Başarılı mı, başarısız mı?

**Kısa cevap:** bugünkü deney başarılı; projenin genel hedefine göre ise kısmen başarılı. Sağlam bir temel
var, ama asıl soru henüz cevaplanmadı.

### Bugünkü deney (27 Eylül 2026: deterministik yeniden koşu ve ters yön testi)

| Soru | Sonuç | Değerlendirme |
|---|---|---|
| CNN sonuçları tekrarlanabilir mi? | Evet, aynı seed bit düzeyinde aynı sonuç | ✅ Başarılı |
| A rölesindeki sonuç sağlam mı? | 94.6–99.4 %, en fazla 3 yanlış açma (önceden 22'ye kadar) | ✅ Başarılı, iyileşti |
| CNN ters yön arızalarını "anlıyor" mu? | Hiç görmediği 1.387 arızanın hiçbirinde açmadı | ✅ Başarılı |
| Overfitting var mı? | Yok | ✅ Başarılı |
| B rölesinde güvenilir sonuç var mı? | Hayır, sıfır yanlış açmada 45–77 % arası dağınık | ❌ Başarısız, ama nedeni bulundu |
| CNN başka röleye taşınabiliyor mu? | Hayır | ❌ Başarısız (beklenen) |

Deneyin asıl amacına ulaşıldı: sayılar dürüst ve tekrarlanabilir. B'deki başarısızlık da bir bulgu: nedeni
bölme kuralı değil, kararsız eğitim ile tek bir en yüksek skora bağlı eşik.

### Projenin genel hedefleri

| Hedef | Durum | Değerlendirme |
|---|---|---|
| Taylor'ın yöntemini doğru kurmak (CVXPY tasarım aracı) | İki baralı modelde doğru, "imkânsız" sonucu kanıtlı; 14 baralı örnek tekrarlanmadı | 🟡 Kısmen |
| Standart invertörlerde yöntem işe yarıyor mu | IEEE 2800'e uyan invertör sinyali 3–17 kat yutuyor | 🟡 Önemli bulgu, yöntem için kötü haber |
| ML ile klasik röle karşılaştırması (gerçek EMT verisi) | CNN, klasik rölenin göremediği yüksek dirençli arızaları sıfır yanlış açmayla yakalıyor; A'da net, B'de kararsız | 🟡 Kısmen, bir rölede net başarı |
| Değerlendirme protokolü | Kuruldu; eski sonuçlardaki birçok hatayı yakaladı | ✅ Başarılı |
| **Asıl soru: yardımcı sinyal invertör ağırlıklı şebekede korumayı iyileştiriyor mu?** | Uygun veri olmadığı için test edilmedi | ⬜ Henüz cevap yok |

### Genel hüküm

- **Başarısız değil:** yayımlanabilir, dürüst ve tekrarlanabilir sonuçlar var (değerlendirme protokolü,
  klasik rölelerle karşılaştırma, doğru kurulmuş tasarım aracı, A rölesindeki niş, ters yön sonucu).
- **"Başardık" demek için erken:** başlıktaki soru cevapsız; iki bulgu yöntemin aleyhine (standart
  invertörler sinyali yutuyor; doğru hata modeliyle basit durumda sinyale gerek kalmıyor).
- **En dürüst ifade:** "Temel sağlam, bazı yanlış iddialar erken yakalandı, bir rölede güçlü bir sonuç var.
  Asıl soruya geçmek için doğru veri gerekiyor" (CigreMV 20 kV, Taylor'ın 14 baralı modeli).

*Kaynak: `results/ADAPTGRID.md` §4–5, `results/DESIGN.md` §4.1.1 ve §4.4, `REVIEW.md` §1 ve §10, bu
dosyanın 6. ve 15–17. soruları.*

---

## 19. Kıdemli bir ML mühendisi ve bir güç/koruma mühendisi (Hasan'ın yöntemini denerken) nelere dikkat eder?

### ML mühendisi

| Konu | Neden önemli | Bizde durum |
|---|---|---|
| Sızıntı | Test bilgisi eğitime karışırsa sonuç şişer | Yük grubuna göre bölme var. Yeni risk: "arıza yok" sınıfı için arıza öncesi pencereler aynı simülasyondan; aynı simülasyonun pencereleri **aynı fold'da** kalmalı |
| Ön işleme yalnızca eğitimde | Ölçekleyici, polinom, öznitelik seçimi | **En önemli yeni risk:** "en iyi 100 öznitelik" seçimi teste bakılarak yapılırsa sızıntı olur; her fold'da yalnızca eğitim verisiyle |
| Hiperparametre seçimi | Teste bakarak seçilen ayar iyimserdir | C iç fold'larda seçilecek |
| Adil karşılaştırma | Bir modele ayar yapıp diğerine yapmamak haksızlık | CNN hiç ayarlanmadı; SVM'in **varsayılan ve ayarlı** iki sürümü raporlanacak |
| Aşamalı sistemde hata yayılması | Tip yanlışsa yanlış zone modeli çalışır | Testte **tahmin edilen** tip; uçtan uca ölçüm |
| Eşik ve skor | SVM olasılık değil mesafe verir | Sıfır yanlış açma eşiği fold dışı skorlardan |
| Tekrarlanabilirlik | Aynı kod aynı sonuç | `random_state` sabit; yakınsama uyarıları kontrol |
| Önceden kayıt | Sonucu görüp ayar değiştirmek kendini kandırmak | Protokol koşmadan önce commit edilecek |
| Belirsizlik | Tek sayı yanıltır | Güven aralığı, seed yayılımı |
| Birim testleri | Sessiz hatalar | Açı referansı, pencere ortalaması, fold içi seçim için testler |

### Güç / koruma mühendisi

| Konu | Neden önemli | Bizde durum |
|---|---|---|
| Fazör doğruluğu | DC ofset, pencere, ilk çevrimdeki geçici rejim | Akımlarda mimic filtresi, testlerle doğrulanmış |
| Açı referansı | Mutlak açı anlamsız; röleler polarizasyon (bellek) kullanır | Arıza öncesi V₁'e göre referans |
| Birimler | kV/kA ile per-unit karışırsa model yükü öğrenir | Hasan mutlak büyüklük kullanıyor; yük 2.8 kat değiştiği için **per-unit sürümü** de denenecek |
| Karar süresi | Zone 1 hızlı olmalı (iletimde tipik hedef 1–1.5 çevrim) | Hasan'ın 2–2.5 çevrimi zone 1 için yavaş; iki sürede ölçülecek, raporda yazılacak |
| Güvenlik sınıfları | Ters yön, sonraki hat, anahtarlama, inrush, CVT | Hepsi ayrı sayılıyor |
| Sınır davranışı | %85 sınırında fazla erişim riski | %85–100 koruma bandı ayrı raporlanıyor |
| Arıza direnci, topraklama | Yüksek direnç en zor durum | Banda ve topraklamaya göre raporlanıyor |
| Ölçüm trafoları | CT/VT hataları, front-end | Röle front-end'i ve cihaz uyumsuzluğu zinciri; SVM de bunlarla test edilecek |
| Yön elemanı | Ağ şebekede yön belirsizleşir (A rölesi bulgusu) | Yön denetimli ve denetimsiz iki satır |
| Kısayol kontrolü | Model arızayı değil işletme noktasını öğrenebilir | SVM için de arıza öncesi pencere testi (H25) |
| Ayarlanabilirlik | İşletme bunu nasıl ayarlar ve doğrular | Doğrusal SVM'in artısı: katsayılar okunabilir |

### Plana eklenenler
1. Öznitelik seçimi ve ölçekleyici her fold'da yalnızca eğitim verisiyle.
2. Arıza öncesi pencereler kendi simülasyonuyla aynı fold'da.
3. Tahmin edilen tiple uçtan uca değerlendirme.
4. SVM'in varsayılan ve ayarlı sürümleri.
5. Büyüklükler için mutlak (Hasan) ve per-unit (uyarlama) sürümleri.
6. Protokolün koşmadan önce commit edilmesi.
7. SVM için kısayol testi, cihaz uyumsuzluğu testi, yön denetimli/denetimsiz satırlar.
8. 2.5 çevrimin zone 1 için yavaş olduğunun raporda açıkça yazılması.

*Kaynak: Hasan ve ark. 2026 (§4.2, §5); `results/ADAPTGRID.md` §3; `REVIEW.md` (H18, H21, H22, H25).*

---

## 20. CIGRE MV deneyinin sonucu bizim için ne kadar önemli?

**Kısa cevap:** Önemli. TestGrid raporunun "bu veri neyi test edemez" bölümünde (`results/ADAPTGRID.md` §5) eksik diye yazdığımız iki şeyi, yani invertör ağırlıklı rejimi ve ikinci bir şebekeyi, ilk kez test eden deney bu. Projenin asıl sorusunu (enjekte edilen sinyal) ise yine cevaplamıyor.

### Neden önemli
1. **İnvertör ağırlıklı rejime ilk kez giriyoruz.**
   - TestGrid'de invertörler kısa devre gücünün yalnızca %0.14'ü.
   - CIGRE MV'de arızadan 20 ms sonra akım artışının medyan %52'si invertörlerden geliyor (`results/CIGREMV_FACTS.md`).
   - Klasik mesafe koruması tam burada zorlanıyor: invertör akımı 1.2 pu ile sınırlı ve negatif sıra davranışı farklı. Ayar çalışmasında R3 için güvenli bir pozitif erişim bulunamadı.
2. **İkinci bir şebeke, yani genelleme testi.**
   - TestGrid bulgusu 1 şebeke ve 2 röleye dayanıyor (B rölesi kararsızdı).
   - CIGRE MV 20 kV, kablolu, 0.24–4.9 km'lik kısa hatlardan oluşuyor ve 4 yeni röle ekliyor.
   - Jürinin ilk sorusu muhtemelen "başka bir şebekede, invertörlü bir şebekede de böyle mi?" olacak.
3. **Yayınlanmış yöntemle karşılaştırmanın tekrarı.** Hasan'ın SVM'i TestGrid'de sıfır yanlış açma eşiğinde %9–58'e düşmüştü. CIGRE'de bunun tekrarlanıp tekrarlanmadığı test ediliyor.

### Sonucun her hali işe yarar
| Sonuç | Anlamı |
|---|---|
| CNN burada da yüksek kapsama, sıfır yanlış açma | Ana bulgu genelleşiyor |
| CNN burada düşük kalır | TestGrid sonucu şebekeye özgü; "invertörlü ortamda öğrenme de zorlanıyor" dürüst bir sınırlama olur |
| Karışık | Invertör baralarındaki R1/R3 ile diğerlerinin farkı, invertörün etkisini doğrudan gösterir |

### Neyi cevaplamıyor
- Enjekte edilen yardımcı sinyal yok; projenin merkez sorusu bu veride de test edilemiyor.
- Yalnızca şebeke-takipli (grid-following) invertörler var.
- CT/CVT modeli yok, frekans 50 Hz, kanal gecikmesi yok.
- Klasik koruma ayarları kendi çalışma modelimizden geliyor. Bu model R1/R3'te EMT'den |Z1L|'nin 0.24–0.69 katı kadar sapıyor (`results/cigremv/study_validation_ibr.json`), bu yüzden klasik koruma satırı bir belirsizlik taşıyor.
- Hâlâ simülasyon ve aynı üretici ailesi (EvEMTBench); gerçek saha verisi değil.

**Önem sıralaması:** TestGrid ana sonucu > CIGRE MV deneyi > karar süresi / zaman taraması. CIGRE deneyi, ana bulgunun inanılırlığını belirleyen ve raporun sınırlar listesini kısaltan deney.

*Kaynak: `results/ADAPTGRID.md` §4–5; `results/CIGREMV_FACTS.md`; `src/review/ladder_mv.py`; `results/cigremv/study_validation_ibr.json`.*

---

## 21. CIGRE deneyinin cevaplamadığı sınırları nasıl kapatırız?

Beş sınır üç türde. Bir kısmı mevcut veriyle kapanır, bir kısmı yeni veri ya da kendi simülasyonumuzu gerektirir, biri de tamamen kapanmaz ve raporda açıkça yazılır.

### 1. Mevcut veriyle (CIGRE koşusundan sonra, ~1 gün)
| Sınır | Nasıl kapanır |
|---|---|
| Klasik ayarlar kendi çalışma modelimizden geliyor (R1/R3'te 0.24–0.69 pu hata) | **T2 basamağı** çalışma modelinden bağımsız: verinin kendisi üzerinde, fiziksel olarak ayarlanabilir sınır içinde ayarlanan en iyi dörtgen, yani "klasik koruma en iyi ihtimalle bu kadar" sınırı. Ek olarak x_set/R_set ±%20 duyarlılık testi yapılır. Karşılaştırma en temiz R2/R4'te (0.04/0.07 pu). |
| CT modeli yok | `common.ct_saturation` ile 400/1 CT'li ikinci bir koşu. Model simülasyonun içinde değil, sonradan uygulanıyor; raporda böyle yazılır. |
| CVT modeli yok | 20 kV'ta geçersiz: orta gerilimde endüktif VT kullanılır, CVT'nin geçici rejim sorunu yüksek gerilime özgü. TestGrid (110 kV) için `cvt_filter` zaten var. |
| Kanal gecikmesi yok | Sonradan uygulanır: uzak ucun kararı 5/10/20 ms geciktirilir, "kanal koptu" durumu eklenir. İki uçlu satır iyimser üst sınır olmaktan çıkar. |

### 2. Yeni veriyle
- **50 Hz → 60 Hz:** EvEMTBench IEEE 39-bus 345 kV şebekesi, setteki tek 60 Hz sistem (`docs/PLAN.md` WP2). Aynı boru hattı değişmeden çalışır. 60 Hz'de bir çevrim 16.7 ms, 50 Hz'de 20 ms. İş ~1–2 gün, çoğu bilgisayar süresi.

### 3. Kendi EMT simülasyonumuzla (projenin asıl işi)
- **Enjekte edilen sinyal** ve **şebeke-kurucu (GFM) invertör** aynı yoldan çözülür; hiçbir açık veri setinde yoklar.
  - Yol A: Taylor'ın 2026 reachability makalesindeki Simulink IEEE 14-bus modeli (akım sınırlayıcılı 5 GFM invertör; Baeckeland ve ark.). PLAN'da hocaya sorulacak 1 numaralı soru.
  - Yol B: Modeli kendimiz kurmak (Simulink/Simscape ya da PSCAD); önce iki baralı örneği EMT'ye taşımak. Birkaç haftalık iş.
  - Her iki yolda da çıktı EvEMTBench etiket şemasıyla uyumlu üretilirse mevcut boru hattının tamamı (ön uç, ayar merdiveni, CNN, Hasan, protokol) değişmeden kullanılır.
- Şimdiye kadarki iş, enjeksiyonsuz durumun sağlam ölçümü. Proje sorusu bu adım olmadan cevaplanmaz.

### 4. Tamamen kapanmayan
- **Simülasyon ve aynı üretici ailesi.**
  - Kısmen azaltılabilir: PROTECT-90 (farklı ekip, farklı üretici), ya da Taylor'ın laboratuvarı üzerinden HIL testi veya gerçek röle kayıtları (COMTRADE).
  - Gerisi lisans projesi için normal bir sınır ve raporda açıkça yazılır. Gürbüzlük testleri (gürültü, ölçü trafosu hatası, cihaz uyumsuzluğu, CT) bu sınırı daraltır.

### Önerilen sıra
1. CIGRE raporu.
2. Hızlı kazanımlar: ayar duyarlılığı, CT'li koşu, kanal gecikmesi.
3. 39-bus 60 Hz.
4. Enjeksiyon + GFM (Taylor'ın modeline bağlı).

*Kaynak: `docs/PLAN.md` (WP2, danışmana sorular, riskler); `results/ADAPTGRID.md` §4–5; `src/review/common.py` (`ct_saturation`, `cvt_filter`); `src/review/ladder.py` (T2).*

---

## 22. CIGRE sonucunun esas fikrimize (yardımcı sinyal enjeksiyonu) katkısı ne? Şimdi ne bekliyoruz, girdi-çıktı ne?

**Kısa cevap:** Deney, esas fikrin çözmeye çalıştığı sorunun EMT verisinde gerçek olduğunu gösteriyor. Enjeksiyonun kendisini test etmiyor; enjeksiyonun aşması gereken çıtayı ve nerede test edilmesi gerektiğini ölçüyor.

### Esas fikir: girdi ve çıktı
- **Girdi:** şebeke modeli ve belirsizlik kümeleri (arıza yeri, R_f, uzak uç akımı, gürültü).
- **Ara adım:** arızanın ölçümde üretebileceği bölge hesaplanır; iç ve dış arıza bölgeleri çakışıyorsa arızalar "belirsiz"dir.
- **Çıktı:** invertörün basacağı en küçük negatif sıra sinyali δ (CVXPY) ve ayrışma garantisi.

### Katkılar
1. **Teorinin öngördüğü belirsizlik EMT'de ölçüldü.**

   | | Oyuncak model | EMT verisi |
   |---|---|---|
   | Güçlü kaynak | `easy`: 0/30 belirsiz, δ = 0 | TestGrid: sınır her R_f diliminde ayrılıyor (AUC 1.000) |
   | Zayıf kaynak / invertör | 5–10/30 belirsiz, δ 0.4–1.3 pu | CIGRE MV: sınır ayrılmıyor (AUC 0.37–0.90), verideki her R_f diliminde (1 Ω altı arıza neredeyse yok, sıfır dirençli arıza test edilemedi) |

   Bu kesin bir ispat değil, güçlü bir işaret: belirsizlik bizim detektörlerimizle ölçüldü, ama beş farklı yöntem aynı yerde başarısız.
2. **Çıta belirlendi:** pasif tek uçlu en iyi sonuç ≤%16, iki uçlu %75–82 (sıfır yanlış açmada; R1/R3 düzeltilmiş etiketlerle). Enjeksiyonun iddiası: kanal kullanmadan, tek uçtan iki uçlu seviyeye yaklaşmak.
3. **Test yeri belirlendi:** invertör barasındaki kısa kablo röleleri (R1/R3) ve sınırdaki arızalar (uzak bara, sonraki hattın ilk %20'si).
4. **Taylor modelinde olmayan üç şey bulundu:**
   - akım sınırlayıcının doğrusal olmaması (çalışma modelinde |Z1L|'nin 0.24–0.69 katı kadar hata);
   - invertörün devreden çıkmasının "ileri yönlü" bir arıza gibi görünmesi;
   - gerçekçi invertör parametreleri (`ibr_study`: k1 1.9–2.6, y2 ≈ 2.4∠−72°, Imax 1.2 pu).

### Beklentiler (enjeksiyonlu simülasyonla test edilecek)
- **H1:** δ ile sınırdaki ayrışma AUC 1'e yaklaşır ve sıfır yanlış açmadaki kapsama ≤%16'dan yukarı çıkar.
- **H2 (en büyük risk):** Arıza sırasında invertör zaten 1.2 pu sınırında; δ = 0.4–1.3 pu için yer kalmayabilir. Arızaların ne kadarında invertörün sınırda olduğu CIGRE verisinde şimdi ölçülebilir.
- **H3:** Gürültü artışının belirsizliği büyütmesi gerçekçi röle ön ucuyla doğrulanacak.

### Aşamaların girdi-çıktısı
| Aşama | Girdi | Çıktı | Durum |
|---|---|---|---|
| WP1 Tasarım | Dizi ağı, invertör modeli, belirsizlik kümeleri | δ ve garanti, ya da "mümkün değil" | Oyuncak model var |
| WP2 Simülasyon | δ | Enjeksiyonlu EMT dalga şekilleri | Taylor'ın modeli ya da kendi modelimiz |
| WP3 Tespit | 20 ms'lik 3 faz V ve I | Açma kararı ve metrikler | Hazır (bugünkü boru hattı) |
| WP4 Gömülü | Detektör | Karar süresi | CNN gecikmesi ölçüldü |

### Önerilen köprü adımı
Taylor'ın tasarım aracını CIGRE'nin gerçek dizi ağına (`setting_study` / `ibr_study`) uygulamak, belirsizlik kümelerini veriden almak (R_f 0–50 Ω, yük ×2.3, röle gürültüsü) ve şunları cevaplamak:
1. δ = 0 iken statik model belirsizlik öngörüyor mu? EMT'deki ölçümle karşılaştırılır; teorinin EMT'ye karşı ilk kontrolü.
2. Hangi δ gerekiyor?
3. Bu δ invertörün payına sığıyor mu (H2)?

Bunun için aracı iki baradan çok baraya genişletmek gerekiyor (PLAN WP1'deki 14-bus kilometre taşı).

*Kaynak: `README.md`; `docs/PLAN.md` WP1–WP4; `results/CIGREMV.md`; `results/cigremv/ibr_characterisation.json`; `results/cigremv/diagnostics.json`.*

---

## 23. B rölesi neden genelde kötü sonuç veriyor?

**Kısa cevap:** B genel olarak kötü değil. Kötü olan tek bir sayı: CNN'in sıfır yanlış açmadaki kapsaması oynak (%45–77). Sebep modelin kendisi değil, eşiğin nasıl belirlendiği: eşiği birkaç nadir dış arıza belirliyor.

### B birçok konuda A'dan iyi
| | A | B |
|---|---|---|
| Klasik zone 1 (R2) | %6 | %13 |
| Hasan, kendi kuralıyla | %82 | %92 |
| 32P/32Q arka arızayı "ileri" görme | 41/188 | 0/1000 |
| CNN, 2.845'te ≤1 yanlış açma | – | %90–98 (6 çekiliş) |
| CNN, sıfır yanlış açma | %94.6–99.4 | %45–77, oynak |

### Mekanizma
1. Sıfır yanlış açmada eşik, eğitimdeki ~2.845 dış arızanın en yüksek puanına konuyor. Bu bir uç değer istatistiği.
2. B'de en yüksek puanlı dış arızalar, uzak baradaki (bus 3) iki neredeyse sıfır dirençli (0.2–1 Ω) arıza: puanları 9.5 ve 6.0, geri kalanların hepsi 1.2'nin altında (`cigremv_diagnostics.py`, `results/cigremv/diagnostics.json`).
3. Bu arızalar bir fold'un eğitim kısmına düşerse eşik yükseliyor. Fold'lar arasında eşik 4.1–17.6 arasında değişti; kapsama düşük eşikte %93–95, en yüksek eşikte %29. Loqo'da dört fold'un hepsine bu arızalardan biri düştü ve sonuç %45 oldu (`splitdiag_adapt_B_relayfe.json`).
4. A'da iç arızaların 168/168'i en yüksek dış arıza puanının üstünde; B'de 156/207. A'da eşik oynasa da kapsama %92–100 kalıyor.

### Neden bu arızalar iç arızaya benziyor
- **Fizik:** Uzak baradaki sıfır dirençli arıza ile %85'teki iç arıza arasındaki fark, hat empedansının yalnızca %15'i (~1.6 Ω). İkisi de büyük akım ve derin gerilim çöküşü üretiyor.
- **Veri:** Bu tür arızalar nadir (R_f medyanı 25 Ω; B'de ≤1 Ω'luk iç arıza yalnızca 5 tane).
- **Not:** CNN'in bu iki arızaya neden yüksek puan verdiği ölçülmüş değil, hipotez. Ölçülen: eşiği bunlar belirliyor ve kapsama eşiği izliyor.
- **Çürütülen hipotez:** "Yük akışı yönü değişiyor" fikri. B'de akış yönü tüm veride yalnızca 1.3° değişiyor.

### Ders
Sıfır yanlış açmalı çalışma noktası, birkaç uç örneğe bağlı gürültülü bir tahmin. B için dürüst rapor, "2.845'te ≤1 yanlış açma" noktasının binom üst sınırıyla (~600'de 1) verilmesi; orada sonuç kararlı (%90–98).

**CIGRE ile bağlantı:** CIGRE'de de eşiği uzak bara ve sonraki hattın başındaki arızalar belirliyor. B'de bu birkaç nadir arıza (küçük, kararsız çakışma); CIGRE'de sınırdaki arızaların tamamı (büyük, kararlı çakışma).

*Kaynak: `results/ADAPTGRID.md` §4 ("Why relay B's answer moves", Q4, "Reverse faults held out"); `results/ADAPTGRID_FACTS.md`; `results/cigremv/diagnostics.json`.*

---

## 24. İki uçlu korumayı (two-ended) bizden başka deneyen var mı?

**Kısa cevap:** Evet. İki uçlu korumayı biz icat etmedik; onlarca yıldır iletim hatlarında standart. Bizim yaptığımız farklı şey, onu tek uçlu yöntemlerle aynı açık veride, aynı sıfır yanlış açma kuralıyla yan yana ölçmek.

### Tek uçlu ve iki uçlu farkı
A–B hattı, iki ucunda birer röle:
- **Tek uçlu:** A'daki röle yalnız kendi gerilim ve akımına bakar ve "arıza hattın %85'inin içinde mi?" sorusunu tek başına cevaplar. CIGRE'de çöken bu.
- **İki uçlu:** A ve B bir kanal (ör. fiber) üzerinden haberleşir. Her röle yalnızca "arıza önümde mi, arkamda mı?" diye bakar; bu mesafe ölçmekten çok daha kolay. İkisi de "önümde" derse arıza aralarındadır ve hat açılır. Arıza B'nin ötesindeyse B "arkamda" der, açma olmaz.

### Başkaları ne yaptı
- **Sahada:** POTT, DCB ve hat diferansiyeli (87L) gibi şemalar iletimde yaygın. Kısa orta gerilim hatları da pratikte çoğunlukla diferansiyel veya haberleşmeli şemalarla korunuyor (`results/CIGREMV.md` §3).
- **İnvertörlü şebekeler:** Literatürde yaygın kanı, iki uçlu şemaların invertörden daha az etkilendiği; tek uçlu mesafe rölesi ve bazı yön elemanları sorun çıkarıyor. Bildiğimiz kadarıyla IEEE 2800 de yön elemanları çalışabilsin diye invertörlerden dengesiz arızada negatif bileşen akımı istiyor (kaynak metinden doğrulanmadı).

### Bizim sonucumuz
CIGRE'de 67N/67Q iki uçta %75–82, hiç yanlış açma yok; POTT eşdeğeri %81–99. Ama iki koşulla: kanal gecikmesi kadar geç açıyor (20 + d ms), ve 67N/67Q'nun sıfırı yeterli boyutta akım trafosu istiyor (hızlı kontroller, `results/cigremv/quick_checks.json`).

### Neden yine de tek uçlu önemli
İki uçlu şema kanal ister: maliyet, birkaç ms gecikme, kanal koparsa çalışmaz. Dağıtım fiderlerinin çoğunda kanal yok ve kanal düştüğünde yedek yine tek uçlu zone 1. Taylor'ın yardımcı sinyali, kanal olmadan tek uçtan bu seviyeye yaklaşmayı hedefliyor.

*Kaynak: `results/CIGREMV.md` §3 ("What still works", "Quick checks"); `results/cigremv/TABLES.md` A; REVIEW.md §7 satır 39–40.*

---

## 25. Pozitif bir sonucumuz var mı?

**Kısa cevap:** Var, ama hepsi güçlü şebekeden ya da iki uçlu şemalardan. İnvertörlü şebekede tek uçlu tarafta pozitif sonuç yok.

| Sonuç | Sayı | Nerede |
|---|---|---|
| Güçlü 110 kV şebekede tek uçlu CNN, sıfır yanlış açma | %94.6–99.4 (röle A, üç tohum, iki bölme), klasik zone 1 %5–13 | `results/ADAPTGRID.md` |
| CIGRE'de iki uçlu 67N/67Q, sıfır yanlış açma | %75–82 (R1'de düzeltilmiş etiketlerle %81.9) | `results/CIGREMV.md` §3 |
| İnvertörde sinyal için yer | 0.4 pu, tek bir tasarım açısında, iç arızaların %77–78'inde 40 ms'de sığıyor | `results/cigremv/ibr_headroom.json` |

**Değişmeyen negatif:** CIGRE'de tek uçlu hiçbir yöntem %15.8'i geçmiyor. R1/R3 etiket düzeltmesinden sonra da bu iki rölede tek uçlu yöntemler en fazla %3.5.

**Dikkat:** Birinci satır "öğrenme işe yarar" demek değil: aynı kuralla gradient boosting %11'e düşüyor ve sonuç TestGrid'e özgü (REVIEW.md §7 satır 26). Üçüncü satır statik bir hesap; invertörün sinyale kendi tepkisi modellenmedi.

*Kaynak: `results/ADAPTGRID.md`; `results/CIGREMV.md`; REVIEW.md §7 satır 26, 37, 41.*

---

## 26. B1 taraması neyi ölçtü ve ne çıktı?

**Kısa cevap:** B1, modelde bir iç arızayı ona en çok benzeyen dış arızadan ayırmak için invertörün ne kadar büyük bir sinyal (δ) basması gerektiğini ölçtü. Cevap: invertörün karşılayabildiği 0,4 pu, ayrılabilen iç arıza oranını sadece 2–4 puan artırıyor; invertörün tam akımı (1,2 pu) bile 8–13 puan. Bu yüzden bu şebekede δ tasarımına geçmiyoruz.

### Nasıl ölçüldü
- **Model:** CIGRE 20 kV şebekesinin statik modeli (`ibr_study`), karakterize edilmiş invertörlerle.
- **Senaryolar:** İç arızalar hattın %70 ve %85'inde; dış arızalar uzak barada ve sonraki hatların ilk %20'sinde. Dört arıza türü, dört R_f aralığı, üç yük seviyesi, iki topraklama, invertörün iki farklı negatif bileşen davranışı.
- **Ölçüt:** Rölenin 16 ölçüm kanalı (arıza sonrası ve öncesi dizi bileşenleri). Ölçüm hatası kanal başına 0,01 pu. İki arıza, bir kanalda 0,02 pu'dan fazla farklıysa ayrılmış sayılıyor.
- **Sinyal:** δ, 0,2–3 pu büyüklük × 12 açıdan oluşan bir ızgarada doğrudan denendi. Model δ'ya göre doğrusal değil, bu yüzden tahmin yerine her noktada tam çözüm yapıldı.

### Ne çıktı (EMT iç arızalarının bulunduğu hücrelere göre ağırlıklı)

| Modelde ayrılabilen iç arıza | R1 | R2 | R3 | R4 |
|---|---|---|---|---|
| Sinyalsiz | %9,2 | %50,2 | %8,4 | %33,0 |
| δ ≤ 0,4 pu | %13,5 | %54,1 | %10,4 | %37,3 |
| δ ≤ 1,2 pu | %21,3 | %60,6 | %16,7 | %46,4 |

- En az 5 EMT arızası olan her hücre ya sinyalsiz ayrılıyor ya da en zor arızası için 1,2 pu'dan fazlası gerekiyor. Durdurma kuralı R1–R3'te aynen, R4'te özünde sağlandı.
- **Neden:** İç arıza (%85) ile uzak bara arızası arasında hattın sadece 0,3–0,6 Ω'u var. Sinyal iki arızanın ölçümünü neredeyse aynı miktarda değiştiriyor.

### Dikkat
Tarama sinyal lehine iyimser: her arızaya kendi en iyi açısı veriliyor, ölçüm hatası sadece cihaz hatası (modelin kendi hatası, B2, eklenmedi) ve model statik. Model R2'de iç arızaların yarısını sinyalsiz bile ayrılabilir sayıyor, oysa EMT'de tek uçlu hiçbir yöntem sıfır yanlış açmada %8,3'ü geçmiyor. Yani gerçek ihtiyaç bu sayılardan büyük, küçük değil.

### Sonraki adım
Bridge planına göre (`review/bridge/LEAD_REVIEW.md` D): CIGRE'de δ tasarımı (M3) yapılmıyor. Olumsuz sonuç mekanizmasıyla raporlanıyor, tasarım 110 kV TestGrid'de çalıştırılıyor. Bu, Taylor'a soracağımız 4. sorunun ("olumsuz sonuç ilginizi çeker mi?") somut dayanağı.

**Güncelleme (4 Eki 2026):** TestGrid'e taşımak araştırmanın sorusunu cevaplamaz. Orada sinyal zaten gerekmiyor, yani tasarım ancak aracın bir kontrolü olur (Q27). Yön sorusunda da pasif bir eleman dengesiz arızaları sinyalsiz çözüyor (Q29). Sinyal için kalan alan üç fazlı arızalar, I2'yi bastıran invertörler ve invertörün devreden çıkması.

*Kaynak: `results/CIGREMV.md` §3 ("How large δ would have to be"); `results/cigremv/b1_delta_screen.json`; REVIEW.md §7 satır 42.*

---

## 27. B1'den sonra tasarımı 110 kV'a taşımak araştırmamızdan sapmaz mı?

**Kısa cevap:** Ana şebeke yaparsak sapar. 110 kV'ta invertör payı kısa devre kapasitesinin %0,14'ü ve sınır zaten sinyalsiz ayrılıyor (CNN %95–99). Orada ne sinyale ihtiyaç var ne de sinyali basacak anlamlı bir invertör. 110 kV ancak bir kontrol olabilir: tasarım aracı, EMT'nin de sinyal gerekmez dediği yerde "gerekmez" diyor mu?

### Araştırmada kalan yol
- **Soruyu değiştirmek, şebekeyi değil.** B1 sadece erişim sorusunu test etti: iç arıza mı, hattın hemen ötesi mi? Bu, sinyalin en zor kullanımı. Taylor'ın Geometry makalesi bile erişimi rölenin karakteristiğine bırakıyor.
- **Yön (ileri / geri):** İnvertör baralarında 32P/32Q iki yönde de yanılıyor. R1'de arkadaki 156 hattın 17 arızasını ileri, 72 iç arızanın 5'ini geri görüyor; R3'te 93'te 9 ve 85'te 12 (`results/cigremv/TABLES.md` H). İleri ve geri arızalar rölenin iki farklı tarafında, elektriksel olarak uzak. Sinyalin fark yaratma şansı erişimdekinden çok daha yüksek. IEEE 2800'ün invertörlerden negatif bileşen akımı istemesinin nedeni de yön elemanları (bildiğimiz kadarıyla; kaynaktan doğrulanmadı). **Güncelleme (Q29):** Pasif bir eleman (Opoku 2025) bu hatayı dengesiz arızalarda sinyalsiz çözüyor. Sinyal ancak üç fazlı arızalarda, I2'yi bastıran invertörlerde ve invertörün devreden çıktığı olaylarda değer katabilir.
- **Arıza türü:** Taylor'ın Geometry makalesindeki asıl kullanım.
- **Taylor'ın 14 baralı modeli:** İnvertörlü bir şebeke. Gelirse erişim sorusunu daha uzun hatlarda deneyebiliriz.

### Olumsuz sonucun yeri
"Kısa MV hatlarda erişim için invertörün basabileceği sinyal yetmiyor" bir araştırma sonucu. Hemen ardından "ama yön için yetiyor mu?" sorusu gelirse sonuç tek başına kalmaz.

*Kaynak: `results/CIGREMV.md` §1, §3; `results/cigremv/TABLES.md` H; `review/bridge/LEAD_REVIEW.md` D; REVIEW.md §7 satır 42.*

---

## 28. Yeni makaleler (okuma listesi K) yön fikrimiz hakkında ne diyor?

**Kısa cevap:** Bulgumuz (invertör barasında 32Q iki yönde yanılıyor) iletim seviyesinde zaten belgelenmiş. "İnvertör negatif bileşen akımı bassın, röleler düzgün çalışsın" fikri de yeni değil; IEEE 2800 bunu zaten istiyor. Bizim savunabileceğimiz katkı daha dar: akım bütçesi içinde kalan ve belirsizlik kümeleri üzerinden ayırma garantisi olan, tasarlanmış bir δ. Bu δ, iki invertörlü bir dağıtım fiderinde, yüksek arıza direncinde, yön ve faz seçimi için birlikte kullanılacak.

### Ne okuduk (20 makale, tamamı; notlar `papers/notes/G1`–`G4`)
- **Mekanizma (G1):** PES-TR81, Haddadi 2021 ve Chowdhury & Fischer Part I aynı sonuca varıyor. İnvertörün negatif bileşen "kaynak empedansı" bir kontrolcü ürünü: I2 küçük ve V2'ye göre açısı endüktif değil. Bu yüzden 67Q/32Q ters arızayı ileri, iç arızayı geri görebiliyor. Akım sınırlayıcı I2'yi kısıyor; TR81'e göre 0,8 pu yükte yaklaşık 0,45 pu kalıyor, bu da bizim 0,4 pu'luk bütçemizle uyumlu.
- **Çözümler (G1, G2):**
  - IEEE 2800 kuralı (I2, V2 ile orantılı ve 90–100° önde): iletimde 32Q'yu düzeltiyor. Davi 2023'te faz-faz arızasında %100, faz-toprakta %90; hatalar yüksek toprak direncinde.
  - Kontrolcüler (Yang/Popov 2023, Azzouz/Hooshyar 2019, Medhat/Azzouz 2022, Banaiemoqadam 2020): invertörü senkron makine gibi gösteriyorlar. Hiçbirinde belirsizliğe karşı garanti yok; hepsi güçlü şebeke ve düşük arıza direnciyle test edilmiş.
  - Röle tarafı (SEL): 32Q'nun devreye girme eşiğini 1,25·IMAX'e çıkarıyor. **Uyarı:** bu ayarla bizim 0,4 pu'luk sinyalimiz röleye hiç görünmez. Sinyal tasarımı ile röle ayarı birlikte düşünülmeli.
- **En yakın rakipler (G3):**
  - Saleh 2021: ileri/geri ayrımı için harmonik deseni optimizasyonla seçiyor; nominal model, ada modu.
  - Yang, Dyśko 2024: sabit 0,3 pu I2'yi 80 ms basıyor; ada modu, tek faz-toprak arızasını ancak ~4–7 Ω'a kadar görüyor.
  - Opoku 2025: pasif bir yön elemanı; enjeksiyonun gerekli olduğunu söylemeden önce bizim veride denemeliyiz.
- **Teori (G4):** Scott 2014, Xu 2023, Nikoukhah 1998 ve Taylor'ın TAC 2025 Teorem 1'i aynı şeyi söylüyor. Gereken sinyal ≥ (2ε − ölçüm farkı) / N; N, iki hipotezin sinyale verdiği tepkinin farkı. Erişimde (iç arıza ile hemen ötesi) N ≈ 0, yani sinyal çok büyük olmalı; B1 bunu gösterdi. Yönde iki hipotez işaret değiştirdiği için N büyük; umut verici. (Güncelleme, Q29: Yönde pasif bir eleman dengesiz arızaları zaten çözüyor; sinyalin işi üç fazlı arızalarla sınırlı.) Kapalı çevrim (Raimondo 2016) garantisini açık çevrimden alıyor; açık çevrim ayıramıyorsa o da kurtarmıyor.

### Sonraki adımlar
1. Opoku'nun pasif yön elemanını EMT verimizde denemek (enjeksiyon gerekli mi?).
2. SEL'in PSV50 blok mantığını invertör devreden çıkma olaylarında denemek.
3. B1'i teorideki formülle yeniden hesaplamak; ızgara yerine doğrudan en küçük sinyal.
4. Yön için B1 taraması: ileri ve geri arıza kümeleri.

*Kaynak: `papers/README.md` K; `papers/notes/G1_mechanism_industry.md`, `G2_control_remedies.md`, `G3_injection_distribution.md`, `G4_theory.md`; REVIEW.md §7 satır 42–43.*

---

## 29. Pasif bir yön elemanı (Opoku 2025) invertör baralarındaki yön hatasını çözüyor mu?

**Kısa cevap:** Dengesiz arızalarda evet, tamamen çözüyor. Üç fazlı arızalarda ve invertörün devreden çıkmasında çözmüyor. Yani yön için sinyal enjeksiyonu ancak bu kalan durumlarda ya da negatif bileşen akımını bastıran invertörlerde gerekli.

### Ne denedik
- Opoku vd. 2025'in elemanı: ΔY2 = ΔI2 / ΔV2, yani arıza öncesine göre negatif bileşen akımı ve gerilimindeki değişimin oranı.
  - Açısı 45° ile 225° arasındaysa "ileri", değilse "geri".
  - Sadece dengesiz arızalarda devreye giriyor (|I2| ≥ 0,1 |I1|).
- Bizim 32P/32Q ile aynı fazörler, aynı arıza kümeleri, 20 ms. 32P/32Q satırları `TABLES.md` H'yi birebir verdi; karşılaştırma tutarlı.

### Sonuç (20 ms)
| | R1: 32P/32Q → ΔY2 | R3: 32P/32Q → ΔY2 |
|---|---|---|
| Dengesiz iç arıza "ileri" | 58/58 → 58/58 | 60/60 → 60/60 |
| Dengesiz arka arıza yanlışlıkla "ileri" (bara + arka hatlar) | 6 + 17 → **0 + 0** | 4 + 3 → **0 + 0** |
| Üç fazlı iç arıza "ileri" | 9/14 → 0/14 | 13/25 → 4/25 |

- 110 kV'taki A rölesinde de 32P/32Q'nun ters yön hatalarını büyük ölçüde siliyor (21 ve 113 → 0 ve 14).
- **Kalan sorunlar:**
  - Üç fazlı arızalar: negatif bileşen olmadığı için eleman kör. (Güncelleme, Q30: Aynı fikrin pozitif bileşen versiyonu bunu da ilk çevrimde çözüyor.)
  - Bara 3'teki invertörün devreden çıkması: R2'de 227/227, R4'te 123/227 olayı "ileri arıza" sanıyor.
  - Transformatör inrush akımı: rölelerde 2. harmonik kilidiyle çözülür, bunu modellemedik.
- **Önemli şart:** Eleman, verideki invertörler negatif bileşende tepki verdiği için çalışıyor. İleri arızalarda |ΔY2| ≈ 9–10 pu; bu, invertörlerin düşük gerilimdeki ~11 pu'luk negatif bileşen davranışıyla uyumlu. I2'yi bastıran bir invertörde (PES-TR81 ve Haddadi'deki "coupled control" durumu) ölçecek bir şey kalmazdı.

### Araştırmaya etkisi
"İnvertör barasında yön için tasarlanmış sinyal gerekir" fikri daraldı (REVIEW.md §7 satır 44). Sinyalin değer katabileceği yerler:
1. Üç fazlı arızalar: röleye negatif bileşen sinyali sağlar.
2. I2'yi bastıran invertörler.
3. İnvertör açma gibi arıza olmayan olayları ayırmak. Bunun için ayrıca bir blok mantığı da gerekebilir; SEL'in PSV50'si bir örnek.

*Kaynak: `results/CIGREMV.md` §3 ("A passive directional element at the inverter buses"); `results/cigremv/opoku_direction.json`; `src/review/opoku_direction.py`; REVIEW.md §7 satır 44.*

---

## 30. Üç fazlı arızada yön için sinyal gerekiyor mu?

**Kısa cevap:** Hayır, iki ayrı kanıtla. Modelde üç fazlı ileri ve geri arızalar sinyal olmadan da birbirinden çok uzak. EMT verisinde de Opoku fikrinin pozitif bileşen versiyonu (ΔY1) üç fazlı arızalarda yönü ilk çevrimde doğru buluyor. Yani bu veride invertör baralarındaki yön sorunu sinyalsiz çözülüyor. Geriye kalan asıl açık sorun, invertörün devreden çıkmasının arıza gibi görünmesi.

### 1. Model taraması (`b1_direction_screen.py`)
- B1'in modeli ve yöntemi aynen kullanıldı; sadece kümeler değişti:
  - İleri: kendi hattında %10, %50 ve %85'te üç fazlı arızalar.
  - Geri: röle barasında ve arkadaki hatlarda üç fazlı arızalar.
- Sonuç: dört rölede, her arıza direnci aralığında, sinyalsiz bile karışan çift yok (ölçüm hatası 0,02 pu'ya çıkarılsa bile).
- Ayrım pozitif bileşen akımından (I1) geliyor. En yakın çiftler bile 0,40–0,53 pu uzakta, yani hata eşiğinin 20 katı.

### 2. EMT verisi (`opoku_direction.py`)
- ΔY1 = ΔI1 / ΔV1, Opoku'yla aynı açı sektörü.
  - Algılama gerilimle yapılıyor (pozitif bileşen geriliminde %5 değişim). Akımla algılama, invertör beslemeli rölede yüksek dirençli arızaları kaçırıyor.
- R1 ve R3'teki bütün üç fazlı iç arızalarda açı doğru sektörde (84°–149°).
- "ΔY2 veya ΔY1 ileri diyorsa ileri" kuralıyla, 20 ms:

| | R1 | R3 | R2 | R4 |
|---|---|---|---|---|
| İç arıza "ileri" | 72/72 | 85/85 | 71/72 | 76/76 |
| Arka arıza yanlış "ileri" (32P/32Q'da) | 0 (23) | 0 (16) | 3 (2) | 0 (0) |

- **Dürüstlük notu:** Bu kuralı R3'ü gördükten sonra seçtim. R3'te üç fazlı arızanın ilk çevrimindeki geçici dengesizlik ΔY2'yi yanlış açıyla devreye sokuyordu. Kuralın bedeli R2'de 2, TestGrid A'da 21 ek ters hata. Daha güvenli kural ("ΔY2 devredeyse o, değilse ΔY1") R3'te 6 üç fazlı arızayı kaçırıyor.
- Bu elemanlar ilk çevrim elemanı. 40 ms'de bozuluyorlar; R2'de üç fazlı ters arızaların 21/23'ünü ileri sanıyor. Karar ilk çevrimde kilitlenmeli, Opoku da öyle yapıyor.

### Araştırmaya etkisi
- Bu veride, invertör baralarında yön için sinyal enjeksiyonu gerekmiyor. Hem dengesiz hem üç fazlı arızalar pasif elemanlarla ilk çevrimde çözülüyor (REVIEW.md §7 satır 44).
- Sinyalin hâlâ değer katabileceği yerler:
  1. **Arızayı olaydan ayırmak:** İnvertörün devreden çıkması R2'de 227/227, R4'te 123/227 "ileri arıza" görünüyor. Bu bir yön sorunu değil, "arıza mı, olay mı" sorunu.
  2. **I2'yi bastıran invertörler:** Bu veride yok, ayrı simülasyon gerekir.
- Bir sonraki mantıklı adım, invertörün devreden çıkması için SEL'in PSV50 blok mantığını ya da benzerini verimizde denemek.

*Kaynak: `results/CIGREMV.md` §3 ("A passive directional element at the inverter buses"); `results/cigremv/opoku_direction.json`; `results/cigremv/b1_direction_3ph.json`; `src/review/b1_direction_screen.py`; REVIEW.md §7 satır 44.*

---

## 31. İnvertörün devreden çıkmasını gerçek arızadan ayırabiliyor muyuz?

**Kısa cevap:** Sadece güvenlik payı olmadan. Ayırt eden tek özellik olaydan sonraki akım; aradaki pencere çok dar. Burada sinyal enjeksiyonu da işe yaramaz, çünkü devreden çıkan invertör o fiderdeki tek kaynak. Pratik çözüm, invertörün durumunu rölelere bildiren bir sinyal, yani yine bir haberleşme kanalı.

### Sorun
- Bara 3'teki invertör devreden çıkınca R2 ve R4'te bütün yön elemanları "ileri arıza" diyor. Bu bir hata değil; olay gerçekten ileri yönde bir değişim:
  - 12 MW'lık besleme kayboluyor, hattın akış yönü dönüyor.
  - R2'de gerilim %9–11 düşüyor, akım değişimi iç arızalarla aynı seviyede.
- R1 ve R3'te kendi baralarındaki invertörün devreden çıkması "geri" görünüyor; orada sorun yok.

### Ne denedik (`inverter_trip_supervision.py`, 20 ms)
Bütün eşikleri olaylara bakmadan, mühendislik kuralıyla belirledim:

| Ek koşul | R2 iç arıza | R2 invertör açma "ileri" | R4 iç arıza | R4 invertör açma "ileri" |
|---|---|---|---|---|
| Yok | 71/72 | 227/227 | 76/76 | 123/227 |
| Akım ≥ yük akımı (paysız) | 69/72 | **0** | 75/76 | **0** |
| Akım ≥ 1,2 × yük akımı (standart pay) | 60/72 | 0 | 58/76 | 0 |
| Sıfır bileşen var | 41/72 | 0 | 36/76 | 0 |
| SEL PSV50 | 57/72 | 156 | 55/76 | 123 |

- "Yük akımı", invertör devre dışıyken ve yük en yüksekteyken röleden geçen akım. Modelden hesaplandı: 0,229 Imax.
- İnvertör açmada olaydan sonraki akım en fazla 0,20 Imax, iç arızalarda en az 0,23 Imax. Paysız eşik bu dar pencereye düşüyor. Normalde konan %20 pay yüksek dirençli arızaları kaybettiriyor.
- Sıfır bileşen kontrolü faz-faz ve üç fazlı arızaları göremiyor. PSV50 bu olay için tasarlanmamış, işe yaramıyor.

### Araştırmaya etkisi
- Bu olay sinyal tasarımıyla çözülemez: devreden çıkan invertör sinyal de basamaz. Sürekli basılan bir "pilot" sinyal, kaybolunca invertörün çıktığını gösterebilirdi. Ama bu bir tür haberleşme olur ve sürekli negatif bileşen basmak güç kalitesi açısından uygun bulunmadı.
- Pratik çözüm: invertör durum sinyaliyle röleyi bloke etmek ya da ayarını değiştirmek. Bu bir kanal ister. Erişim sonucu (B1) da aynı yere çıkmıştı: invertörlü dağıtım fiderinde güvenilir koruma haberleşme istiyor.
- Böylece bu veride sinyal enjeksiyonunun ne erişimde, ne yönde, ne de arıza/olay ayrımında açık bir değeri kalmadı. Açık kalan tek durum I2'yi bastıran invertörler; o da bu veride yok (REVIEW.md §7 satır 42, 44, 45). Modelde test ettik: Soru 32.

*Kaynak: `results/CIGREMV.md` §3 ("Telling a fault from an inverter disconnecting"); `results/cigremv/inverter_trip_supervision.json`; `src/review/inverter_trip_supervision.py`; REVIEW.md §7 satır 45.*

---

## 32. Negatif bileşen akımını bastıran invertörlerde yön bozuluyor mu, bir sinyal düzeltiyor mu?

**Kısa cevap:** Bozuluyor. Küçük bir sinyal de düzeltiyor, ama yalnızca arızadan sonra ölçülen V2'ye göre ayarlanan türü. Önceden tasarlanıp invertörün kendi çerçevesinde sabitlenen bir sinyal düzeltmiyor. Düzelten davranış, IEEE 2800'ün invertörlerden zaten istediği şey: I2'yi V2'nin 90° önünde basmak. Ek olarak küçük V2'de yeterli kazanç gerekiyor; bu standardın açık bıraktığı bir ayar.

### Neden bu test
- Yön sonucumuz (Soru 29–30) bir şeye dayanıyordu: veri setindeki invertörler arızada negatif bileşen akımı basıyor, ΔY2 elemanı da bunu ölçüyor.
- Eski tip ("coupled control") invertörler I2 basmaz, yani I2 = 0. Veride böyle invertör yok. Bu yüzden testi B1'in statik modelinde yaptık: aynı şebeke, yük durumları, topraklama ve arıza dirençleri.
- Taylor'ın sinyali için bu veride kalan tek boşluk buydu (Soru 31'in sonu).

### Ne çıktı (`i2_suppressed_direction.py`, dengesiz arızalar, "ΔY2 devredeyse ΔY2, değilse ΔY1" kuralı)

| İnvertör davranışı | R1 iç arıza "ileri" | R3 iç arıza "ileri" | R4 arkadaki arıza "ileri" (hata) |
|---|---|---|---|
| Kayıttaki gibi (kontrol) | %95,5 | %91,4 | %2,4 |
| I2 bastırılmış | **%74,2** | **%51,9** | **%32,1** |
| Bastırılmış + V1'e göre sabit sinyal (en iyi genlik ve açı) | %90,1 | %68,0 | %9,9 |
| Bastırılmış + V2'nin önünde 0,1 pu (küçük V2'de k = 5) | %99,6 | %99,7 | %0,8 |
| IEEE 2800, k = 6 | %99,7 | %100 | %0 |
| IEEE 2800, k = 2 | %94,2 | %87,4 | %3,2 |

- **Bastırınca yön bozuluyor.**
  - R1 ve R3'te iç arızaların bir kısmı kaçıyor, çünkü ΔY2 devreye giremiyor (R3'te hiç).
  - R4'te arkadaki arızaların üçte biri "ileri" sanılıyor; bu bir güvenlik hatası.
  - R2 etkilenmiyor.
- **V1'e göre sabit sinyal düzeltmiyor.**
  - Her röle için 48 genlik/açı denemesinin en iyisini sonradan seçtik; hiçbiri yetmiyor.
  - Sinyal büyüdükçe kötüleşiyor. R2 ve R4'te 0,1 pu ve üstü, arkadaki arızaların %30–46'sını "ileri" yapıyor.
  - Sebep: arızada V2'nin V1'e göre açısı arıza tipine ve dirence göre değişiyor. V1'e göre sabitlenmiş bir akım, ΔV2'ye karşı her arızada başka bir açıda kalıyor.
- **V2'ye göre ayarlanan sinyal düzeltiyor.**
  - Sinyalin büyüklüğü 0,1 pu yetiyor.
  - Belirleyici olan, V2'nin en küçük olduğu yüksek dirençli arızalardaki kazanç. Kazanç 2'de kalırsa sonuç IEEE k = 2 satırıyla aynı oluyor, yani yarım çözüm.
  - Kazançsız, her V2'de sabit 0,1 pu basan sürüm V2 sıfıra yaklaşınca tanımsız. Model R4'teki arızaların beşte birinde çözülemedi, o yüzden o satırı kullanmadık.

### Araştırmaya etkisi
- **Olumlu taraf:** sinyal fikrinin bu veride işe yaradığı ilk yer burası. Sinyal gerekiyor ve küçük bir sinyal yetiyor.
- **Ama gereken sinyal kapalı çevrim.** Arızadan sonra ölçülen V2'ye göre ayarlanıyor. Bu, IEEE 2800'ün zaten istediği davranış; gereken kazanç (küçük V2'de yaklaşık 5) ise bir ayar. Taylor'ın tasarımının açık çevrim biçimi, yani önceden seçilip invertörün çerçevesinde sabitlenen δ, işe yaramıyor.
- **Pratik çözüm:** bir şebeke kodu gereksinimi ("I2'yi V2'nin önünde, yeterli kazançla bas"), tasarlanmış bir δ değil.
- **Taylor'a sorulacak soru:** Tasarım çerçevesi V2'ye göre ayarlanan, yani geri beslemeli bir sinyal üretebilir mi? Yoksa bu durumda doğru araç şebeke kodu mu?
- **Sınırlar:**
  - Statik model; EMT'de denenmedi.
  - Sinyal akım sınırlayıcıdan sonra eklendi; 0,1 pu sığıyor.
  - Sadece ilk çevrimdeki fazör elemanları test edildi.

*Kaynak: `results/CIGREMV.md` §3 ("Inverters that suppress negative-sequence current"); `results/cigremv/i2_suppressed_direction.json`; `src/review/i2_suppressed_direction.py`; REVIEW.md §7 satır 46.*

---

## 33. Sinyal hiçbir yerde işe yaramadı; sorun veride mi?

**Kısa cevap:** Veride bir hata yok. Sonucu belirleyen şey, verinin temsil ettiği şebeke türü. Kısa hatlı, 20 kV'luk, şebekeyi izleyen (grid-following) invertörlü bir dağıtım fiderinde Taylor'ın yöntemine iş kalmıyor. Bu, yöntemin başka bir şebekede de çalışmayacağı anlamına gelmiyor.

### Verinin hatası değil
- Bulduğumuz veri sorunlarını düzelttik ya da kontrol ettik:
  - R1/R3'teki konum etiketi hatası (REVIEW.md §7 satır 41);
  - arıza öncesi etiket sızıntısı (satır 25).
- Düzeltmelerden sonra sonuçlar değişmedi.

### Sonucu şebekenin kendisi belirliyor
- **Erişim:** Hatlar çok kısa. Hattın %85'indeki arıza ile uzak baradaki arıza arasında sadece 0,3–0,6 Ω var. Sinyal ikisini de aynı miktarda kaydırıyor. Bunu Taylor'ın kendi Teorem 1'i de öngörüyor; hangi veriyi kullansak, kısa hatlı bir fiderde aynısı olur.
- **Yön:** Bu invertörler arızada zaten I2 basıyor (IEEE 2800'ün istediği gibi). O yüzden yön sinyalsiz çözülüyor.
- **İnvertörün devreden çıkması:** Çıkan invertör sinyal de basamaz. Bu mantıksal bir sonuç, veriye bağlı değil.
- **I2 bastıran invertörler:** Önceden sabitlenmiş sinyalin işe yaramamasının sebebi de genel: V2'nin açısı arıza tipine göre değişiyor.

### İki şebeke, iki uç
- TestGrid (110 kV, güçlü şebeke): sınır sinyalsiz zaten ayrılıyor, δ'ya gerek yok.
- CIGRE MV (20 kV, kısa hatlar, invertörlü): δ gerekiyor ama yetmiyor.
- Yöntemin yeri büyük ihtimalle ikisinin arası: daha uzun hatlar ve zayıf, invertör ağırlıklı kaynaklar. Şebeke kurucu (grid-forming) invertörlü sistemler de aday.

### Verinin gerçek sınırları
- Hiçbir kayıtta enjekte edilmiş sinyal yok. Sinyalli sonuçlarımızın hepsi statik modelden; EMT'de doğrulanmadı.
- Sadece şebekeyi izleyen invertörler var; şebeke kurucu yok.
- Sadece iki şebeke var; uzun hatlı, invertörlü bir şebeke yok.

### Ne yapmalı
- Uzun hatlı ya da şebeke kurucu invertörlü bir şebekede, sinyali gerçekten basan EMT simülasyonları.
- En iyi aday Taylor'ın 14 baralı modeli. Bu yüzden görüşmede hat verisini ya da Simulink modelini istiyoruz.

*Kaynak: `results/CIGREMV.md` §3–§5; `results/ADAPTGRID.md`; REVIEW.md §7 satır 25, 41, 42, 44–46; Soru 26, 31, 32.*

---

## 34. Taylor'ın yönteminin (tasarlanmış sinyal δ) nerede çalışmasını umuyoruz?

**Kısa cevap:** Üç koşulun bir arada olduğu yerde: uzun hat, invertör ağırlıklı (zayıf) kaynak ve haberleşme kanalı olmaması. Sinyalin biçimi de önemli: ölçülen gerilime göre ayarlanan, kapalı çevrim bir sinyal olmalı. Bu henüz bir hipotez; açık veride bu koşulları birlikte taşıyan şebeke yok.

### Neden bu üç koşul
Her koşul, yöntemin bizim iki şebekemizde neden işe yaramadığından çıkıyor:

| Koşul | Neden gerekli | Dayanak |
|---|---|---|
| Uzun hat | İç arıza ile hemen ötesindeki arızanın sinyale farklı tepki vermesi için aralarında yeterli hat empedansı olmalı. CIGRE MV'de bu fark sadece 0,3–0,6 Ω. | B1 (Soru 26), Taylor'ın Teorem 1'i |
| İnvertör ağırlıklı kaynak | Güçlü şebekede sınır sinyalsiz zaten ayrılıyor, sinyale gerek kalmıyor. | TestGrid 110 kV (δ = 0'da ayrılıyor) |
| Haberleşme kanalı yok | Kanal varsa iki uçlu şemalar zaten çalışıyor (%75–82). Sinyalin değeri, tek uçlu bir çözüm olması. | CIGRE MV iki uçlu sonuçları |

### Sinyalin biçimi
- I2 bastıran invertör testinde önceden sabitlenen sinyal işe yaramadı. Arızadan sonra ölçülen V2'ye göre ayarlanan sinyal işe yaradı (Soru 32).
- Yani yöntemin şansı, sinyali ölçüme göre ayarlayan, geri beslemeli bir tasarımda.
- IEEE 2800 bu davranışı iletime bağlı invertörlerden istiyor. Dağıtıma bağlı invertörler için bildiğimiz kadarıyla böyle bir zorunluluk yok. Tasarlanmış bir sinyalin anlam kazanabileceği yer orası.

### Somut aday
- Kırsal 34,5–69 kV hatlar: uzun (onlarca km), ucunda büyük bir güneş ya da rüzgâr santrali, fiber kanalı yok.
- Şebeke kurucu (grid-forming) invertörlü sistemler. Taylor'ın 14 baralı modeli bu türden ve yöntem orada geliştirildi.

### Nerede çalışmasını beklemiyoruz
- Kısa kablolu, 20 kV'luk kent içi dağıtım fiderleri (CIGRE MV).
- Güçlü, senkron kaynaklı iletim şebekeleri (TestGrid). Orada zaten bizim öğrenen detektörümüz (CNN) %95–99 yakalıyor.

> **Güncelleme:** Uzun hat hipotezini modelde kaba bir taramayla test ettik; 3 kata kadar desteklenmedi. Bkz. Soru 36.

### Nasıl kontrol ederiz
1. **Modelde, hemen:** B1 taramasını hatları uzatılmış CIGRE MV modelinde tekrar koşmak. Sinyalin erişime katkısı hat boyuyla artıyor mu?
2. **EMT'de:** Taylor'ın 14 baralı modelinde ya da kendi simülasyonumuzda sinyali gerçekten basmak.

*Kaynak: Soru 26, 31–33; `results/CIGREMV.md` §3–§4; `results/ADAPTGRID.md`; REVIEW.md §7 satır 42, 44–46.*

---

## 35. Soru 34'teki koşulları (uzun hat, invertör ağırlıklı kaynak) sağlayan veri setleri hangileri?

**Kısa cevap:** Hazır veri olarak hiçbiri ikisini birden tam sağlamıyor, ve hiçbirinde sinyal basılmamış. "Haberleşme kanalı yok" koşulu verinin değil, bizim değerlendirmemizin özelliği: her veri setinde röleyi tek uçlu çalıştırabiliriz. Sinyali gerçekten test etmek için model gerekiyor; veri seti yetmiyor.

| Kaynak | Uzun hat | İnvertör ağırlıklı | Sinyal eklenebilir mi | Not |
|---|---|---|---|---|
| EvEMTBench multigrid 110 kV | Kısmen: hatlar 1–32 km | Kısmen: kaynakların yarısı invertör olabilir, ama dış şebeke 800–8.000 MVA, invertörler 20–50 MVA | Hayır | Bizim formatımız, kodumuz çalışır; 105 rastgele topoloji; henüz indirilmedi |
| EvEMTBench multigrid 345 kV | Evet: 1–111 km | Hayır: invertör yok | Hayır | Sadece senkron makineler |
| IRTSD (PNNL) | Muhtemelen (230/500 kV); hat uzunluğu sayfada yazmıyor | Kısmen: yaklaşık %40 invertör | Evet: PSCAD modeli açık ve değiştirilebilir | 5.500 olay, 29,6 GB, CC BY 4.0; PSCAD lisansı gerekir; 60 Hz |
| PNNL T&D test sistemi | Belirtilmemiş | GFL + GFM invertör modelleri | Evet (model) | Sadece model ve 3 örnek, olay verisi yok; PSCAD |
| PV santrali hatları (IEEE 9 bara, DataPort) | Belirtilmemiş | PV santrali | Hayır | Sadece akım var, gerilim yok: mesafe rölesi için kullanılamaz; ücretli |
| PROTECT-90 | 90 kV çift hat | Hayır: invertör yok | Hayır | Ölçüm zincirini doğrulamak için |
| Taylor'ın 14 baralı modeli (Baeckeland) | Belirtilmemiş | Evet: şebeke kurucu | Evet | Yazarlardan istenmesi gerekiyor |

### Ne anlama geliyor
- **Pasif yöntemleri uzun hatta denemek için:** EvEMTBench multigrid 110 kV. Uzun hattı ve invertöre yakın olan topolojileri seçebiliriz. Ama invertörler yine GFL ve zaten I2 basıyor; sinyal testi yapılamaz.
- **Sinyali test etmek için:** sinyali basabileceğimiz bir model gerekiyor. Seçenekler:
  1. Kendi statik modelimizde hatları uzatıp B1'i tekrar koşmak. En ucuzu, hemen yapılabilir; ama EMT değil.
  2. Taylor'ın 14 baralı modeli. En uygun, şebeke kurucu; ama istememiz gerekiyor.
  3. IRTSD'nin PSCAD modeli. Açık, iletim seviyesi; ama PSCAD lisansı gerekiyor.

*Kaynak: `papers/notes/D_ml_and_datasets.md` §15–16; Soru 13–14; EvEMTBench makalesi (arXiv:2608.19777, multigrid parametreleri); IEEE DataPort sayfaları: IRTSD (DOI 10.21227/mp6d-j677), PNNL T&D modeli (DOI 10.21227/z3r5-p932), "Transients in transmission lines connected to Photovoltaic Farms".*

---

## 36. Hatları uzatınca sinyal erişime daha çok yardım ediyor mu?

**Kısa cevap:** Modelde 3 kata kadar hayır. Hat uzayınca asıl sinyalsiz (pasif) ölçüm iyileşiyor. İnvertöre sığan 0,4 pu'luk sinyalin katkısı her uzunlukta küçük kalıyor (1–11 puan). Soru 34'teki "uzun hat" hipotezi bu modelde desteklenmedi.

### Ne yaptık (`b1_long_lines.py --coarse`)
- B1 taramasını, korunan hat ve ötesindeki hatlar 2 ve 3 kat uzun olacak şekilde tekrarladık. Başka hiçbir şeyi değiştirmedik.
- 10 kat denedik ama olmadı: 20 kV'luk fider o uzunlukta invertörün gücünü taşıyamıyor ve arıza öncesi yük akışı çözülmüyor. Model bunu sessizce geçiyordu; artık betik kontrol ediyor.
- Izgara kaba. Sinyalsiz ayrılabilirliği olduğundan yüksek, sinyalin katkısını olduğundan düşük gösteriyor. Ama bu sapma her uzunlukta aynı, o yüzden sadece eğilime bakıyoruz.

### Ne çıktı (sinyalsiz ayrılabilen iç arıza oranı · 0,4 pu'nun eklediği · 1,2 pu'nun eklediği)

| Röle | ×1 | ×2 | ×3 |
|---|---|---|---|
| R1 | %19 · +3 · +13 | %34 · +3 · +14 | %55 · +8 · +10 |
| R2 | %54 · +3 · +17 | %76 · +1 · +6 | %81 · +5 · +8 |
| R3 | %20 · +2 · +7 | %30 · +2 · +12 | %32 · +3 · +15 |
| R4 | %47 · +6 · +11 | %59 · +4 · +10 | %64 · +11 · +19 |

- **Pasif ölçüm hızla iyileşiyor:** ×1'den ×3'e 12–35 puan.
- **Sinyalin katkısı aynı hızda büyümüyor:**
  - 0,4 pu sadece R1 ve R4'te, ×3'te biraz artıyor.
  - 1,2 pu'nun katkısı rölelere göre artıyor ya da azalıyor; ortak bir eğilim yok.
- **Anlamı:** hat uzadıkça sınır, sinyal işe yaramaya başlamadan önce pasif olarak ayrılabilir hale geliyor. Bu da önceki tabloyla uyumlu: güçlü ve uzun hatlı şebekede (TestGrid) sinyale gerek yoktu.

### Sınırlar
- Kaba ızgara.
- Sadece 3 kata kadar: hatlar 6–12 Ω, iç arızanın ucu ile uzak bara arası en fazla 1,74 Ω.
- Statik model, EMT değil; 20 kV.
- Gerçekten uzun hatlar (yüksek gerilimde onlarca km) bu modelle test edilemiyor. Onun için Taylor'ın modeli ya da IRTSD gerekiyor (Soru 35).

*Kaynak: `results/CIGREMV.md` §3 (B1, "Longer lines"); `results/cigremv/b1_long_lines_coarse.json`; `src/review/b1_long_lines.py`; REVIEW.md §7 satır 47.*

---

## 37. Taylor'a mailde söylediğimiz iddialar doğrulandı mı?

**Kısa cevap:** Eğilimler doğrulandı, kesin sayılar tam doğrulanmadı. Güçlü kaynakta sinyal gerekmiyor, zayıf kaynakta gerekiyor, gürültü artınca çok daha fazlası gerekiyor: bunlar tutuyor. "0,4–0,7 pu" ve "1 pu'yu geçiyor, invertör veremez" ise modellemeye çok bağlı.

| Mailde dediğimiz | Durum | Ayrıntı |
|---|---|---|
| Tasarımı CVXPY ile iki baralı örnekte yeniden kurduk | Yapıldı | `src/aux_signal_toy.py` (CVXPY + Clarabel). Aracın bulduğu sinyaller tam en küçük değil: 0,51 pu yerine kesin minimum 0,50 pu (REVIEW.md §7 satır 1, 5) |
| Güçlü senkron kaynakta sinyal gerekmiyor | Tutuyor | Bu iki baralı modelde kanıtlı (satır 2). 110 kV gerçek EMT verisinde de aynısı çıktı |
| Zayıf kaynak/invertörde yüksek dirençli toprak arızaları ayrılamıyor, ~0,4–0,7 pu gerekiyor | Kısmen | Ayrılamama doğru (30 arızanın 5–7'si). Akım sınırı olmayan modelde 0,50–0,69 pu: mailde dediğimiz. Ama sayı modele bağlı: %10 güvenlik payıyla 0,67–1,36 pu; açı belirsizliği doğru modellenince 0,55–1,05 pu; invertörün faz başına akım sınırı probleme eklenince 0,16–0,26 pu (B5). O küçük sinyalleri her durumda basmak için de invertörün faz başına 1,4–1,8 pu verebilmesi gerekiyor (satır 1, 3) |
| Gürültü %50 artınca iki kat daha çok belirsiz durum, sinyal 1 pu'yu geçiyor, invertörün verebileceğinden fazla | Tutuyor | İki kat doğru (30'da 5 → 10). Akım sınırı olmayan modelde 1,32 pu. Sınır faz başına doğru eklenince (B5) 1,2 pu'da güvenceli bir tasarım yok: en küçük aday 0,72 pu, arıza noktalarının arasında tutmuyor; onu basmak için de faz başına ~1,9 pu gerekir. Ara kontroldeki "0,76 pu ile çözülür" yanlıştı (satır 4) |
| İkimizin ISAIA'da kabul edilmiş makalesi var | Repoda yok | Kontrol edilemedi |

**Not (B5, 5 Oct 2026):** Akım sınırlı sayılar düzgün yeniden koşuldu. Ara kontrol (0,20–0,32 pu ve ~0,76 pu), gerçekte invertörün taşıyamayacağı akımları da kabul eden gevşek bir kural kullanmıştı. Doğru per-faz kuralıyla 0,16–0,26 pu ve %50 fazla gürültüde güvenceli tasarım yok (`results/DESIGN.md` §3, §4.1; REVIEW.md §7 satır 3–4).

### Görüşmede sorulursa
> "In the email I quoted 0.4–0.7 pu; that holds without the current limit. With the inverter's per-phase limit inside the problem it drops to about 0.16–0.26 pu, but injecting it on top of the inverter's own current needs 1.4–1.8 pu per phase. With 50 % more noise we find no certified design at a 1.2 pu limit."

*Kaynak: README.md ("What is already here"); REVIEW.md §7 satır 1–6; `results/DESIGN.md` §3, §4.1; `review/WP1_REPORT.md`; `results/CIGREMV.md` §3 ("Room in the inverter").*

---

## 38. Taylor'ın hangi makaleleri NSF'yi ve NREL'i anıyor?

**Kısa cevap:** Taylor'ın 2025–2026 makalelerinin hepsi aynı NSF projesinden fonlanıyor (Grant 2411925). NREL ise Nathan Baeckeland üzerinden geliyor: Baeckeland NREL'de ve şebeke kurucu (GFM) invertör modelini yapan kişi. Yani maildeki iki seçenek, "NSF projenizin simülasyon altyapısı" ve "NREL modelleri", büyük ihtimalle birbirine yakın.

### NSF (Grant 2411925)
| Makale | NSF teşekkürü |
|---|---|
| Active Fault Detection in Static Systems (IEEE TAC, 2025) | Var |
| Geometry of Distance Protection (2025) | Var |
| Distance Characteristics with Incremental Quantities (2026) | Var |
| Reachability-based Time-domain Distance Protection (2026) | Var |
| Auxiliary Signal Based Distance Protection (2023) | Metinde bulunamadı |

### NREL
- **Reachability-based Time-domain Distance Protection (2026):** ortak yazar Nathan Baeckeland. Makalede NREL'in yeni adıyla, "National Laboratory of the Rockies" olarak geçiyor; DOE sözleşme numarası (DE-AC36-08GO28308) NREL'inki.
- **Baeckeland, Yang & Seo (2026, IEEE TPWRS), "Unified Model for Current-Limiting GFM Inverters":** tamamen NREL çalışması. Şebeke kurucu invertör modeli ve 14 baralı Simulink test sistemi buradan.

### Görüşme için
Taylor "Nathan'ın modeli" ya da "Baeckeland'ın modeli" derse, NREL'in şebeke kurucu invertör modelini kastediyor. Onun simülasyonları büyük ihtimalle bu modele dayanıyor.

*Kaynak: makalelerin teşekkür ve yazar satırları (`papers/Taylor_2025_Geometry_of_Distance_Protection.pdf`, `papers/Taylor_2026_*.pdf`, `papers/library/Taylor_2025_Active_Fault_Detection_Static_Systems.pdf`, `papers/library/Baeckeland_2026_Unified_Model_Current_Limiting_GFM_Inverters.pdf`); `papers/notes/A_taylor_line.md` §5.*

---

## 39. Projede invertörün amacı ne?

**Kısa cevap:** İki rolü var. Arıza akımını sınırladığı için mesafe rölesini yanıltıyor, yani sorunun kaynağı. Ama çıkışı yazılımla kontrol edildiği için Taylor'ın tasarlanmış sinyalini (δ) basıp röleye yardım edebiliyor, yani çözümün aracı.

### 1. Şebekedeki normal işi
Güneş paneli, rüzgâr türbini ve batarya DC ya da düzensiz bir akım üretir. İnvertör bunu şebekenin 50/60 Hz AC'sine çeviren güç elektroniği cihazı; yenilenebilir santrallerin şebekeye bağlandığı kapı.

### 2. Neden sorun yaratıyor
- Dönen jeneratörler arızada normal akımlarının 5–10 katını verir; mesafe rölesi arızayı bu büyük akımdan ve gerilim düşümünden anlar.
- İnvertör kendini korumak için akımını en fazla ~1,2 pu'da tutar (normalin %20 fazlası).
- Röle arızayı göremeyebilir ya da yerini yanlış hesaplayabilir. İnvertör arttıkça sorun büyüyor.

### 3. Taylor'ın fikrinde çözümün parçası
İnvertöre arızada küçük, tasarlanmış bir negatif bileşen akımı (δ) bastırılıyor. Bu sinyal arızaları röle için ayırt edilebilir yapıyor.

### 4. Projede invertörle ne yapıyoruz
Gerçek bir invertör kullanmıyoruz, modelliyoruz:
- açık veride (EvEMTBench) invertörlerin arızadaki davranışını inceledik;
- kendi modellerimizde δ basmayı hesapladık;
- önerdiğimiz EMT simülasyonunda invertör modeli δ'yı gerçekten basacak ve röle/detektörlerin bunu yakalayıp yakalamadığını test edeceğiz.

*Görüşmede:* "The inverter is both the cause and the cure: it limits fault current, which confuses distance relays, but because it is software-controlled it can also inject the designed signal that helps them decide."

*Kaynak: Soru 1, 34; `results/CIGREMV.md` §1 (invertörlerin arıza akımı payı); `papers/notes/A_taylor_line.md`.*
