"""TA-008 matematik ve geometri uzmanlığı. Saf Python + sınırlı SymPy; sağlayıcı çağırmaz.

SymPy kullanan bütün işlevler yalnız MathAI'nin yalıtılmış işçi sürecinde (``mathai.worker``) çalışır.
İfadeler yalnız ``integrity.expression`` ayrıştırıcısı ve ``mathai.parser.to_sympy`` ile kurulur;
``eval``/``exec``/``sympify``/``parse_expr`` kullanılmaz. AST'ye dayalı hafif analiz (``guidance``) süreç
içinde ve SymPy'siz çalışır.
"""
