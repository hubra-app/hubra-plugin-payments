import { Navigate, useLocation } from 'react-router-dom'
import { registerPlugin } from '@hubra/plugin-sdk'
import { PayButton } from './PayButton'
import { LIST_PATH, PaymentsScreen, SETTINGS_PATH } from './PaymentsScreen'
import { ReturnScreen } from './ReturnScreen'
import translations from './translations.json'

/** The old addresses open Finanzen, keeping ?connected=1 and the like. */
function MovedTo({ to }: { to: string }) {
  const { search } = useLocation()
  return <Navigate to={`${to}${search}`} replace />
}

registerPlugin({
  id: 'payments',
  routes: [
    { path: 'payments', module: 'payments', perm: 'payments.account.manage', component: () => <MovedTo to={LIST_PATH} /> },
    { path: 'payments/settings', module: 'payments', perm: 'payments.account.manage', component: () => <MovedTo to={SETTINGS_PATH} /> },
    // Every member comes back here from Stripe.
    { path: 'payments/return', module: 'payments', component: ReturnScreen },
  ],
  // Online payments are money matters, so they live in Finanzen: the list
  // next to the other bookings, the Stripe account and fees in Finanzen's
  // last tab, Einstellungen, next to Bank & QR-Rechnung.
  tabs: [
    {
      screen: 'finance',
      id: 'online-payments',
      label: 'shell.nav.payments',
      module: 'payments',
      perm: 'payments.account.manage',
      group: 'bookings',
      component: () => <PaymentsScreen part="list" />,
    },
    {
      screen: 'finance',
      id: 'online-payments-settings',
      label: 'shell.nav.payments',
      module: 'payments',
      perm: 'payments.account.manage',
      group: 'setup',
      component: () => <PaymentsScreen part="settings" />,
    },
  ],
  slots: [{ slot: 'invoice.actions', module: 'payments', component: PayButton }],
  translations,
})
