import { getToken, initializeAppCheck, ReCaptchaEnterpriseProvider, type AppCheck } from 'firebase/app-check';
import { firebaseConfigured, getFirebaseAuth } from './firebase';

let attestation: AppCheck | undefined;

// Anahtar verilmezse her çağrı bağımsız yeni bir işlemdir (bkz. idempotency.ts).
export async function requestHeaders(idempotencyKey?: string): Promise<Record<string, string>> {
  const headers: Record<string, string> = { 'Idempotency-Key': idempotencyKey ?? crypto.randomUUID() };
  if (!firebaseConfigured) return headers;
  const auth = getFirebaseAuth();
  await auth.authStateReady();
  if (auth.currentUser) headers.Authorization = `Bearer ${await auth.currentUser.getIdToken()}`;
  const key = process.env.NEXT_PUBLIC_FIREBASE_APP_CHECK_SITE_KEY;
  if (key) {
    attestation ??= initializeAppCheck(auth.app, { provider: new ReCaptchaEnterpriseProvider(key), isTokenAutoRefreshEnabled: true });
    try {
      headers['X-Firebase-AppCheck'] = (await getToken(attestation)).token;
    } catch {
      // The backend applies the configured monitoring or enforcement policy.
    }
  }
  return headers;
}
