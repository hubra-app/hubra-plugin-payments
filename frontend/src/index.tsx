import { Navigate, useLocation } from 'react-router-dom'
import { registerPlugin } from '@hubra/plugin-sdk'
import { PayButton } from './PayButton'
import { PaymentsScreen } from './PaymentsScreen'
import { ReturnScreen } from './ReturnScreen'
import translations from './translations.json'

/** The old address, /app/payments, opens the set-up in Finanzen (keeping ?connected=1 and the like). */
function PaymentsMoved() {
  const { search } = useLocation()
  return <Navigate to={`/app/finance/online-payments${search}`} replace />
}

registerPlugin({
  id: 'payments',
  routes: [
    { path: 'payments', module: 'payments', perm: 'payments.account.manage', component: PaymentsMoved },
    // Every member comes back here from Stripe.
    { path: 'payments/return', module: 'payments', component: ReturnScreen },
  ],
  // The Stripe set-up is a money setting, so it sits in Finanzen ›
  // Einstellungen next to Bank & QR-Rechnung.
  tabs: [
    {
      screen: 'finance',
      id: 'online-payments',
      label: 'shell.nav.payments',
      module: 'payments',
      perm: 'payments.account.manage',
      group: 'setup',
      component: PaymentsScreen,
    },
  ],
  slots: [{ slot: 'invoice.actions', module: 'payments', component: PayButton }],
  translations,
})
