import os

import pytest

# Isolate all tests from local .env, production Firebase and provider credentials.
os.environ["TEACHERAI_ENVIRONMENT"] = "test"
os.environ["TEACHERAI_FIREBASE_ENABLED"] = "false"
os.environ["OPENAI_API_KEY"] = ""
os.environ.pop("ANTHROPIC_API_KEY", None)

# TA-005C: geçit muhasebe kapsamı olmadan sağlayıcı çağırmaz. Sağlayıcı sınıflarını doğrudan (HTTP katmanı
# olmadan) sınayan testler için her test açık bir offline kapsamla başlar. Bu kapsam yalnız sahte
# istemcilerle çalışır, kendi çağrı tavanı vardır ve kullanıcı kotasına yazmaz. HTTP üzerinden giden
# testler kabul katmanının production kapsamını kullanır (TestClient ayrı iş parçacığında çalışır ve bu
# kapsamı görmez). Kapsamsız reddi sınayan testler ``no_accounting_scope`` fixture'ını kullanır.
TEST_SCOPE_MAX_CALLS = 50


@pytest.fixture(autouse=True)
def offline_test_accounting():
    from apps.api.app.core.gateway import begin_offline_accounting, end_accounting
    from apps.api.app.core.settings import get_settings

    token = begin_offline_accounting("pytest", get_settings(), max_calls=TEST_SCOPE_MAX_CALLS)
    try:
        yield
    finally:
        end_accounting(token)


@pytest.fixture
def no_accounting_scope(offline_test_accounting):
    from apps.api.app.core import gateway

    token = gateway._current.set(None)
    try:
        yield
    finally:
        gateway._current.reset(token)
