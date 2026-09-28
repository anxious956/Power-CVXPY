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
