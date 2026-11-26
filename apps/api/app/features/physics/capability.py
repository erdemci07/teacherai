"""TA-009 fizik yetenek sınıfları: *gerçekte* ne yapıldığı (hedef mimari değil).

Sınıf, o konuda ulaşılabilen en güçlü doğrulamadır; tek bir problemin sınıfı ayrıca raporda hesaplanır ve konu adından
çıkarılmaz. ``verified``: belirlenimci çözücü ve koşul/akla yatkınlık/türlü cevap denetimleri var (yine de her problem
için ayrıca geçmelidir). ``partially_checked``: yalnız bir bölüm denetlenir. ``interpreted``: sağlayıcı modeli yalnız
yorumlanır. ``unsupported``: çözücü yok; sağlayıcı denklemlerinin boyut tutarlılığı yine denetlenir ama cevap
doğrulanmış gösterilmez.
"""

ROWS = [
    # alan, konu, sınıf, çözücü/denetleyici, not
    ("Ölçme", "Birimler, önekler, sınav birimleri (km/sa, cal, atm, cmHg, kWh, eV)", "verified", "reasoning.units",
     "Dönüşüm çarpanları BIPM/NIST kaynaklı; °C ötelemeli ölçek dönüştürülmez."),
    ("Ölçme", "Boyut tutarlılığı", "verified", "reasoning.formula.check_dimensions",
     "Boyut uyumu yasanın doğru seçildiğini kanıtlamaz; tutarsızlık maddi çelişkidir."),
    ("Ölçme", "Anlamlı basamak ve ölçüm belirsizliği", "partially_checked", "reasoning.quantities.Policy",
     "Cevap karşılaştırmasında yazılı hassasiyet kullanılır; belirsizlik yayılımı hesaplanmaz."),
    ("Ölçme", "Skaler ve vektör, işaretli bileşen", "verified", "reasoning.quantities.compare",
     "Sürat/hız, büyüklük/bileşen, yön; eksen önce sabitlenir."),
    ("Mekanik", "Sabit hızlı ve sabit ivmeli doğrusal hareket", "verified", "physics.mechanics.solve_kinematics",
     "İvmenin sabitliği kaynakta veya grafikte kurulmalı; aksi halde kısmi."),
    ("Mekanik", "Serbest düşme ve yatay atış", "verified", "physics.mechanics.solve_kinematics",
     "g yalnız soru uzlaşımından veya görünür standart değerden; Dünya dışında uydurulmaz."),
    ("Mekanik", "Hız–zaman grafiği (eğim, alan, alınan yol)", "verified", "physics.graphs.velocity_time",
     "Yalnız basılı değerler; değişen eğimde sabit ivme formülü engellenir."),
    ("Mekanik", "Eğik atış, bağıl hareket", "unsupported", "—", "Bu fazda çözücü yok."),
    ("Mekanik", "Newton yasaları (tek cisim, yatay/eğik düzlem)", "verified", "physics.mechanics.solve_dynamics",
     "Kuvvetler kaynağa bağlanmalı; eylemsiz sistem ve sabit kütle görünür varsayım."),
    ("Mekanik", "Statik ve kinetik sürtünme", "verified", "physics.mechanics.solve_dynamics",
     "Kayma durumu önce f_s ≤ μ_s N ile karar verilir; tek katsayıda eşitlik görünür varsayım."),
    ("Mekanik", "İple bağlı cisimler, makara, Atwood", "verified", "physics.mechanics.solve_dynamics",
     "Kütlesiz ip ve ideal makara görünür varsayım; ikiden çok cisim desteklenmez."),
    ("Mekanik", "Dairesel hareket, kütle çekimi", "unsupported", "—", "Bu fazda çözücü yok."),
    ("Enerji ve momentum", "Kinetik ve potansiyel enerji, iş", "verified", "physics.mechanics.solve_energy",
     "Tek cisim, tek evre."),
    ("Enerji ve momentum", "Mekanik enerji korunumu (sürtünme işi dahil)", "verified", "physics.mechanics.solve_energy",
     "Sürtünmeli yüzeyde korunum yalnız sürtünme işi hesaba katılarak."),
    ("Enerji ve momentum", "Güç, verim", "unsupported", "—", "Akla yatkınlık (0 ≤ verim ≤ 1) denetlenir; çözücü yok."),
    ("Enerji ve momentum", "Momentum, tek doğrultuda çarpışmalar", "verified", "physics.mechanics.solve_momentum",
     "Net dış itme kaynakta yoksayılabilir olmalı; kinetik enerji artışı maddi çelişki."),
    ("Enerji ve momentum", "İtme", "unsupported", "—", "Bu fazda ayrı çözücü yok."),
    ("Dönme ve denge", "Tork, kütle merkezi, statik denge, açısal momentum", "unsupported", "—",
     "Tork ve enerji aynı boyutta olduğundan tür denetimi yapılır; çözücü yok."),
    ("Akışkanlar", "Özkütle, basınç, kaldırma, Pascal, süreklilik, Bernoulli", "unsupported", "physics.laws",
     "Koşullar (durgun akışkan, sıkıştırılamaz, viskozitesiz) tanımlı; çözücü yok."),
    ("Termodinamik", "Isı, öz ısı, hal değişimi, genleşme, ideal gaz, yasalar", "unsupported", "physics.laws",
     "İdeal gaz koşulu (mutlak sıcaklık) tanımlı; çözücü yok; °C dönüştürülmez."),
    ("Elektrik", "Doğru akım devreleri (seri, paralel, Kirchhoff, iç direnç)", "verified", "physics.circuits.solve",
     "Bağlantı grafiğinden değiştirilmiş düğüm analizi; belirsiz bağlantıda hedefli açıklama."),
    ("Elektrik", "Eşdeğer direnç, ampermetre ve voltmetre", "verified", "physics.circuits.equivalent_resistance",
     "İdeal ölçü aletleri görünür varsayım."),
    ("Elektrik", "Elektrik enerjisi ve güç (direnç üzerinde)", "verified", "physics.circuits.solve", "P = I² R."),
    ("Elektrik", "Coulomb, elektrik alanı, potansiyel, sığa", "unsupported", "—", "Bu fazda çözücü yok."),
    ("Manyetizma", "Manyetik alan ve kuvvet, indüksiyon, Faraday, Lenz, transformatör", "unsupported", "—",
     "Bu fazda çözücü yok."),
    ("Dalgalar", "Basit harmonik hareket, dalga, ses, girişim, Doppler", "unsupported", "physics.laws",
     "Sarkaç için küçük genlik koşulu tanımlı; çözücü yok."),
    ("Optik", "Yansıma, kırılma, aynalar, ince mercek", "unsupported", "physics.laws",
     "Paraksiyel yaklaşım ve işaret uzlaşımı koşulu tanımlı; çözücü yok."),
    ("Modern fizik", "Foton, fotoelektrik, enerji düzeyleri, görelilik, yarı ömür", "unsupported", "physics.conventions",
     "Tanımlı sabitler (c, h, e) kaynaklı; çözücü yok."),
]
