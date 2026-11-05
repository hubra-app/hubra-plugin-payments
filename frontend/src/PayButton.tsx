import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@mantine/core'
import { IconCreditCard } from '@tabler/icons-react'
import { useT, useToast, type SlotProps } from '@hubra/plugin-sdk'
import { QK, errorText, getStatus, startCheckout } from './api'

/** "Online bezahlen" next to an open invoice of the signed-in member. */
export function PayButton({ invoice }: SlotProps['invoice.actions']) {
  const { t } = useT()
  const { notify } = useToast()
  const [busy, setBusy] = useState(false)
  const status = useQuery({ queryKey: QK.status, queryFn: getStatus, staleTime: 60_000 })
  const s = status.data
  if (!s?.ready || invoice.status === 'Paid' || Number(invoice.memberId) !== s.memberId) {
    return null
  }
  const pay = async () => {
    setBusy(true)
    try {
      const { url } = await startCheckout(Number(invoice.id))
      window.location.assign(url)
    } catch (err) {
      notify('error', errorText(err))
      setBusy(false)
    }
  }
  return (
    <Button size="sm" variant="filled" loading={busy} onClick={pay} leftSection={<IconCreditCard size={16} />}>
      {t('payments.pay')}
    </Button>
  )
}
