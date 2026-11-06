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
  /** Members pay a surcharge so the club gets the full invoice amount. */
  passFees: boolean
  surchargePercent: number
  surchargeFixed: number
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
  /** A fee comes on top of the invoice for members. */
  passFees: boolean
}

export interface Checkout {
  id: number
  invoiceId: number | null
  memberId: number | null
  memberName: string | null
  amount: number
  fee: number
  /** Paid on top of the invoice (fees passed on). */
  surcharge: number
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
export const saveFees = (body: Partial<Pick<Account, 'passFees' | 'surchargePercent' | 'surchargeFixed'>>) =>
  apiFetch<{ account: Account | null }>(`${BASE}/fees`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

/** What a member pays for an invoice of *amount* CHF (mirrors services.price). */
export function priceFor(amount: number, acc: Account, hubraPercent: number) {
  const cents = Math.round(amount * 100)
  if (!acc.passFees) return cents / 100
  const pct = acc.surchargePercent + hubraPercent
  const fixed = Math.round(acc.surchargeFixed * 100)
  if (pct <= 0 && fixed <= 0) return cents / 100
  return Math.ceil((cents + fixed) / (1 - pct / 100) - 1e-9) / 100
}

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
