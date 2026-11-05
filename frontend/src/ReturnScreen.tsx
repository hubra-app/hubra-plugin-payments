import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { Button, Group, Paper, Stack, Text, ThemeIcon, Title } from '@mantine/core'
import { IconCircleCheck, IconClock, IconX } from '@tabler/icons-react'
import { ErrorBanner, LoadingSpinner, formatCHF, useT } from '@hubra/plugin-sdk'
import { confirmCheckout, errorText } from './api'

type State =
  | { kind: 'loading' }
  | { kind: 'paid'; invoiceId: number | null; amount: number }
  | { kind: 'open' }
  | { kind: 'cancelled' }
  | { kind: 'error'; message: string }

/** Where Stripe sends the member back to, paid or not. */
export function ReturnScreen() {
  const { t } = useT()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [params] = useSearchParams()
  const sessionId = params.get('session_id')
  const [state, setState] = useState<State>(
    sessionId ? { kind: 'loading' } : { kind: 'cancelled' },
  )

  useEffect(() => {
    if (!sessionId) return
    let stop = false
    const check = async (tries: number) => {
      try {
        const r = await confirmCheckout(sessionId)
        if (stop) return
        if (r.status === 'paid') {
          setState({ kind: 'paid', invoiceId: r.invoiceId, amount: r.amount })
          qc.invalidateQueries({ queryKey: ['invoices'] })
          qc.invalidateQueries({ queryKey: ['my-invoices'] })
        } else if (r.status === 'open' && tries > 0) {
          // TWINT can take a moment to confirm.
          setTimeout(() => check(tries - 1), 2000)
        } else {
          setState({ kind: r.status === 'expired' ? 'cancelled' : 'open' })
        }
      } catch (err) {
        if (!stop) setState({ kind: 'error', message: errorText(err) })
      }
    }
    check(4)
    return () => {
      stop = true
    }
  }, [sessionId, qc])

  if (state.kind === 'loading') return <LoadingSpinner />

  const view = {
    paid: {
      icon: <IconCircleCheck size={28} />,
      color: 'green',
      title: t('payments.return.paidTitle'),
      body:
        state.kind === 'paid'
          ? t('payments.return.paidBody', {
              amount: formatCHF(state.amount),
              invoice: String(state.invoiceId ?? ''),
            })
          : '',
    },
    open: {
      icon: <IconClock size={28} />,
      color: 'yellow',
      title: t('payments.return.openTitle'),
      body: t('payments.return.openBody'),
    },
    cancelled: {
      icon: <IconX size={28} />,
      color: 'gray',
      title: t('payments.return.cancelledTitle'),
      body: t('payments.return.cancelledBody'),
    },
    error: { icon: <IconX size={28} />, color: 'red', title: '', body: '' },
  }[state.kind]

  return (
    <Paper withBorder p="xl" maw={520} mx="auto" mt="xl">
      {state.kind === 'error' ? (
        <ErrorBanner message={state.message} />
      ) : (
        <Stack align="center" gap="sm" ta="center">
          <ThemeIcon size={52} radius="xl" variant="light" color={view.color}>
            {view.icon}
          </ThemeIcon>
          <Title order={3}>{view.title}</Title>
          <Text c="dimmed">{view.body}</Text>
        </Stack>
      )}
      <Group justify="center" mt="lg">
        <Button onClick={() => navigate('/app/dashboard/me')}>{t('payments.return.back')}</Button>
      </Group>
    </Paper>
  )
}
