# TA-008B matematik derlemi yerel ölçümü

`python -m scripts.math_matrix` çıktısı. Süreler bu geliştirme makinesinde, süreç içinde (SymPy ısınmış), vaka başına üç koşunun ortancasıdır. Yalıtılmış işçinin süreç başlatma maliyeti (≈ 1–3 sn) dahil değildir. Bulut performansı iddiası değildir.

| Alan | Vaka | Ortanca (ms) | En yavaş (ms) |
| --- | --- | --- | --- |
| algebra | 18 | 29.8 | 170.0 |
| calculus | 8 | 2.1 | 22.3 |
| foundations | 9 | 8.9 | 33.4 |
| functions | 10 | 23.3 | 45.8 |
| geometry | 29 | 5.2 | 117.5 |
| probability | 5 | 0.1 | 0.1 |
| statistics | 1 | 0.1 | 0.1 |
| strategy | 2 | 0.0 | 0.0 |
| trigonometry | 5 | 0.1 | 519.0 |
| word_problems | 10 | 7.7 | 12.0 |

Beklenenle uyuşmayan vaka: 0.
