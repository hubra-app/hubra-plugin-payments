import { registerPlugin } from '@hubra/plugin-sdk'
import { IconCreditCard } from '@tabler/icons-react'
import { PayButton } from './PayButton'
import { PaymentsScreen } from './PaymentsScreen'
import { ReturnScreen } from './ReturnScreen'
import translations from './translations.json'

registerPlugin({
  id: 'payments',
  routes: [
    { path: 'payments', module: 'payments', perm: 'payments.account.manage', component: PaymentsScreen },
    // The page's last tab, Einstellungen: the Stripe account and the fees.
    { path: 'payments/settings', module: 'payments', perm: 'payments.account.manage', component: PaymentsScreen },
    // Every member comes back here from Stripe.
    { path: 'payments/return', module: 'payments', component: ReturnScreen },
  ],
  slots: [{ slot: 'invoice.actions', module: 'payments', component: PayButton }],
  // The nav entry in hubra_payments/__init__.py names this icon.
  icons: { 'credit-card': IconCreditCard },
  translations,
})
