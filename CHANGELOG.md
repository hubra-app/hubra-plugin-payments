# Online payments

## Unreleased

- Online payments moved into Finanzen: the list of payments is
  Finanzen › Buchungen › Online-Zahlungen (`/app/finance/online-payments`),
  the Stripe account and fees are Finanzen › Einstellungen › Online-Zahlungen
  (`/app/finance/online-payments-settings`), Finanzen's last tab. The page
  under Weitere is gone; `/app/payments` and `/app/payments/settings` (and
  Stripe's return links to them) open the new places.

## 1.3.0

The page has two tabs: Zahlungen, the list of online payments, and
Einstellungen (`/app/payments/settings`), with the club's Stripe account and
who pays the fees. Coming back from Stripe's set-up opens Einstellungen. This
follows Hubra's rule that a setting lives on the page it configures, in its
last tab.
## 1.2.2

1.2.1 was tagged but couldn't be signed, so it was never released. 1.2.2 is the same plugin, signed. What it brings:

Changed: the club's connected Stripe account belongs to one Stripe mode.
Hubra now has a sandbox and a live key (and sandbox clubs that always use
the sandbox); an account connected in the sandbox isn't used once the club
runs live, and the other way round. After going live the club connects its
Stripe account once more. Open checkouts are only checked with the key of
their account's mode.

## 1.2.1

1.2.0 was tagged but couldn't be signed, so it was never released. 1.2.1 is the same plugin, signed. What 1.2.0 brings:

Changed: the club's connected Stripe account belongs to one Stripe mode.
Hubra now has a sandbox and a live key (and sandbox clubs that always use
the sandbox); an account connected in the sandbox isn't used once the club
runs live, and the other way round. After going live the club connects its
Stripe account once more. Open checkouts are only checked with the key of
their account's mode.

## 1.2.0

Changed: the club's connected Stripe account belongs to one Stripe mode.
Hubra now has a sandbox and a live key (and sandbox clubs that always use
the sandbox); an account connected in the sandbox isn't used once the club
runs live, and the other way round. After going live the club connects its
Stripe account once more. Open checkouts are only checked with the key of
their account's mode.

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
