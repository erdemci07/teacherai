'use client';

import { useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { EmailAuthProvider, reauthenticateWithCredential, signInWithEmailAndPassword, signOut } from 'firebase/auth';
import { getFirebaseAuth } from '../lib/firebase';
import { useAuth } from '../auth/AuthProvider';
import { DELETED_DATA, deletionView, type DeletionView } from '../lib/account-deletion';
import { AccountApiError, clearLocalState, receiptStatus, rememberReceipt, requestDeletion, storedReceipt, type DeletionState } from '../lib/account-api';

const MAX_ROUNDS = 30;
const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export function AccountDeletion() {
  const { user } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState(user?.email ?? '');
  const [password, setPassword] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [view, setView] = useState<DeletionView | null>(null);
  const busy = useRef(false);

  const finish = async () => {
    clearLocalState();
    try { await signOut(getFirebaseAuth()); } catch { /* hesap zaten silindi */ }
    router.replace('/');
  };

  const show = (state: DeletionState | null, error: string | null = null) => {
    const next = deletionView(state?.status ?? null, state?.failed_step ?? null, error);
    setView(next);
    return next;
  };

  const run = async () => {
    if (busy.current || !confirmed || !password) return;
    busy.current = true;
    const auth = getFirebaseAuth();
    try {
      const current = auth.currentUser;
      if (!current) { show(null, 'reauthentication_required'); return; }
      const uid = current.uid;
      await reauthenticateWithCredential(current, EmailAuthProvider.credential(email, password));
      for (let round = 0; round < MAX_ROUNDS; round += 1) {
        try {
          const state = await requestDeletion();
          if (state.receipt) rememberReceipt(uid, state.receipt);
          if (show(state).kind === 'done') { await wait(1500); await finish(); return; }
        } catch (error) {
          if (!(error instanceof AccountApiError)) throw error;
          if (error.code === 'network_error' || error.code === 'authentication_required') {
            // Yanıt kaybolmuş veya Auth hesabı silinmiş olabilir: sonucu makbuzla doğrula.
            const saved = storedReceipt();
            if (saved) {
              const state = await receiptStatus(saved.uid, saved.receipt).catch(() => null);
              if (state && show(state).kind === 'done') { await wait(1500); await finish(); return; }
            }
            if (error.code === 'network_error') { show(null, 'network_error'); return; }
          } else {
            show(error.state, error.code === 'account_deletion_incomplete' ? null : error.code);
            return;
          }
        }
        // İlk istek yenileme belirteçlerini iptal eder; devam için aynı bilgilerle yeniden giriş yapılır.
        await wait(1500);
        await signInWithEmailAndPassword(auth, email, password);
      }
    } catch {
      show(null, 'reauthentication_required');
    } finally {
      busy.current = false;
    }
  };

  return <section className="panel" aria-labelledby="delete-account">
    <p className="eyebrow">Tehlikeli bölge</p>
    <h2 id="delete-account">Hesabımı sil</h2>
    <p>Bu işlem <strong>geri alınamaz</strong>. Aşağıdakiler kalıcı olarak silinir:</p>
    <ul>{DELETED_DATA.map((item) => <li key={item}>{item}</li>)}</ul>
    <p>Eski sürümde sahibi kaydedilmeden oluşturulmuş bazı paylaşım bağlantıları otomatik silinemez; bunlar işletmeci incelemesiyle yayından kaldırılır.</p>
    <label>E-posta<input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
    <label>Parola<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
    <label><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /> Hesabımın ve tüm verilerimin geri alınamaz biçimde silineceğini anladım.</label>
    {view && <p role="status" className={view.kind === 'error' ? 'errorText' : undefined}>{view.message}</p>}
    <div className="placeholderActions">
      <button type="button" className="dangerButton" disabled={!confirmed || !password || view?.kind === 'working'} onClick={run}>
        {view?.kind === 'error' && view.canRetry ? 'Tekrar dene' : 'Hesabımı kalıcı olarak sil'}
      </button>
    </div>
  </section>;
}
