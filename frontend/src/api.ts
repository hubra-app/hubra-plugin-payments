import { apiFetch } from '@hubra/plugin-sdk'

export interface Account {
  id: string
  name: string | null
  livemode: boolean
  detailsSubmitted: boolean
  chargesEnabled: boolean
  card: boolean
  twint: boolean
  checkedAt: string | null
}

export interface Status {
  /** The platform has a Stripe key. */
  platform: boolean
  testMode: boolean
  /** Members can pay online in this club. */
  ready: boolean
  memberId: number | null
  canManage: boolean
  account?: Account | null
  feePercent?: number
}

export interface Checkout {
  id: number
  invoiceId: number | null
  memberId: number | null
  memberName: string | null
  amount: number
  fee: number
  status: 'open' | 'paid' | 'expired'
  method: string | null
  createdAt: string | null
  paidAt: string | null
}

const BASE = '/app/payments'

export const QK = {
  status: ['payments', 'status'] as const,
  checkouts: ['payments', 'checkouts'] as const,
}

export const getStatus = () => apiFetch<Status>(`${BASE}/status`)
export const connect = () => apiFetch<{ url: string }>(`${BASE}/connect`, { method: 'POST' })
export const refresh = () =>
  apiFetch<{ account: Account | null; ready: boolean }>(`${BASE}/refresh`, { method: 'POST' })
export const disconnect = () => apiFetch<void>(`${BASE}/connect`, { method: 'DELETE' })
export const listCheckouts = () => apiFetch<Checkout[]>(`${BASE}/checkouts`)
export const startCheckout = (invoiceId: number) =>
  apiFetch<{ url: string }>(`${BASE}/invoices/${invoiceId}/checkout`, { method: 'POST' })
export const confirmCheckout = (sessionId: string) =>
  apiFetch<{ status: Checkout['status']; invoiceId: number | null; amount: number }>(
    `${BASE}/checkouts/confirm`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId }),
    },
  )

export function errorText(err: unknown) {
  return err instanceof Error ? err.message : String(err)
}
