# Online payments

## 1.1.0

Added: clubs can pass the fees on to members (Wer zahlt die Gebühren):
members pay a surcharge on top of the invoice, sized from the club's Stripe
rate and the Hubra fee so the club still receives the full invoice amount.
The "platform fee" is now called the Hubra fee.

Fixed: the plugin didn't load in Hubra 0.2.2 and later (the club backend
image no longer ships `hubra.api`), so Online payments never showed up in a
club's modules. Paid invoices are now marked through the
`finance.invoice.set_status` contract. Needs Hubra 0.2.2 or later.

## 1.0.0

First version. Members pay their open invoices online by card or TWINT
through the club's own Stripe account (Stripe Connect, Standard account);
the invoice is marked paid when Stripe confirms the payment. Admins connect
the account, see its state (payments, card, TWINT) and every online payment
under Weitere › Online-Zahlungen. Needs Hubra with the `invoice.actions`
slot and the platform's Stripe key in manage › Payments.
