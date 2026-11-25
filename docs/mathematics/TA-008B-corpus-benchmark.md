# TA-008B matematik derlemi yerel ölçümü

`python -m scripts.math_matrix` çıktısı. Süreler bu geliştirme makinesinde, süreç içinde (SymPy ısınmış), vaka başına üç koşunun ortancasıdır. Yalıtılmış işçinin süreç başlatma maliyeti (≈ 1–3 sn) dahil değildir. Bulut performansı iddiası değildir.

| Alan | Vaka | Ortanca (ms) | En yavaş (ms) |
| --- | --- | --- | --- |
| algebra | 18 | 27.0 | 173.6 |
| calculus | 8 | 2.3 | 25.3 |
| foundations | 9 | 9.4 | 33.6 |
| functions | 10 | 24.3 | 47.7 |
| geometry | 21 | 5.9 | 119.5 |
| probability | 5 | 0.1 | 0.1 |
| statistics | 1 | 0.1 | 0.1 |
| strategy | 2 | 0.0 | 0.0 |
| trigonometry | 5 | 0.1 | 507.0 |
| word_problems | 10 | 7.5 | 12.1 |

Beklenenle uyuşmayan vaka: 0.
