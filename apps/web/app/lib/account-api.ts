import { requestHeaders } from './request-headers';
import type { DeletionStatus } from './account-deletion';

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.NEXT_PUBLIC_TEACHERAI_API_BASE_URL ?? 'http://localhost:8000/api/v1';
const RECEIPT_KEY = 'teacherai.accountDeletionReceipt';

export interface DeletionState {
  status: DeletionStatus;
  completed_steps: string[];
  failed_step: string | null;
  receipt?: string | null;
}

export class AccountApiError extends Error {
  constructor(public code: string, public state: DeletionState | null = null) { super(code); }
}

async function parse(response: Response): Promise<DeletionState> {
  const body = await response.json().catch(() => null);
  if (response.ok) return body.data as DeletionState;
  throw new AccountApiError(body?.error ?? 'account_error', body?.data ?? null);
}

export async function requestDeletion(): Promise<DeletionState> {
  const headers = await requestHeaders();
  try {
    const response = await fetch(`${BASE}/account/deletion`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify({ confirm: true }) });
    return await parse(response);
  } catch (error) {
    if (error instanceof AccountApiError) throw error;
    throw new AccountApiError('network_error');
  }
}

// Auth hesabı silindikten sonra oturum açılamaz; sonuç yalnız makbuzla okunur.
export async function receiptStatus(uid: string, receipt: string): Promise<DeletionState> {
  const response = await fetch(`${BASE}/account/deletion/receipt`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ uid, receipt }) });
  return parse(response);
}

export function rememberReceipt(uid: string, receipt: string) {
  try { sessionStorage.setItem(RECEIPT_KEY, JSON.stringify({ uid, receipt })); } catch { /* özel pencere: makbuz yalnız bellekte kalır */ }
}

export function storedReceipt(): { uid: string; receipt: string } | null {
  try { return JSON.parse(sessionStorage.getItem(RECEIPT_KEY) ?? 'null'); } catch { return null; }
}

export function clearLocalState() {
  for (const storage of [localStorage, sessionStorage]) {
    try { storage.clear(); } catch { /* tarayıcı depolaması kapalı olabilir */ }
  }
}
