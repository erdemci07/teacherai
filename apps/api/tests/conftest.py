import os

# Isolate all tests from local .env, production Firebase and provider credentials.
os.environ["TEACHERAI_ENVIRONMENT"] = "test"
os.environ["TEACHERAI_FIREBASE_ENABLED"] = "false"
os.environ["OPENAI_API_KEY"] = ""
