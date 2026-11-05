# Online payments

## 1.0.0

First version. Members pay their open invoices online by card or TWINT
through the club's own Stripe account (Stripe Connect, Standard account);
the invoice is marked paid when Stripe confirms the payment. Admins connect
the account, see its state (payments, card, TWINT) and every online payment
under Weitere › Online-Zahlungen. Needs Hubra with the `invoice.actions`
slot and the platform's Stripe key in manage › Payments.
