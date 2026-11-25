# TA-008 matematik yerel performans ölçümü

`python -m scripts.math_matrix` çıktısı. Süreler bu geliştirme makinesinde, süreç içinde (SymPy ısınmış), vaka başına üç koşunun ortancasıdır. Yalıtılmış işçinin süreç başlatma maliyeti (≈ 1–3 sn) dahil değildir. Bulut performansı iddiası değildir.

| Alan | Vaka | Ortanca (ms) | En yavaş (ms) |
| --- | --- | --- | --- |
| algebra | 16 | 22.3 | 161.0 |
| calculus | 8 | 2.5 | 25.1 |
| foundations | 3 | 4.2 | 33.7 |
| functions | 6 | 14.5 | 47.6 |
| geometry | 9 | 5.6 | 114.0 |
| probability | 5 | 0.1 | 0.1 |
| statistics | 1 | 0.1 | 0.1 |
| strategy | 2 | 0.0 | 0.0 |
| trigonometry | 5 | 0.1 | 505.1 |
| word_problems | 6 | 7.5 | 12.2 |

Beklenenle uyuşmayan vaka: 0.
