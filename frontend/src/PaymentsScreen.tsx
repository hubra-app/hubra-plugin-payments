import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Badge, Button, Group, NumberInput, Paper, Radio, Stack, Table, Text, Title } from '@mantine/core'
import { IconAlertTriangle, IconBrandStripe, IconRefresh } from '@tabler/icons-react'
import {
  ConfirmModal,
  EmptyState,
  ErrorBanner,
  LoadingSpinner,
  PageHead,
  formatCHF,
  formatDateTime,
  useT,
  useToast,
} from '@hubra/plugin-sdk'
import {
  QK,
  connect,
  disconnect,
  errorText,
  getStatus,
  listCheckouts,
  priceFor,
  refresh,
  saveFees,
  type Account,
} from './api'

function Flag({ on, label }: { on: boolean; label: string }) {
  return (
    <Badge variant="light" color={on ? 'green' : 'gray'}>
      {label}
    </Badge>
  )
}

type FeeEdits = Partial<Pick<Account, 'passFees' | 'surchargePercent' | 'surchargeFixed'>>

/** Who pays the fees: the club, or the members through a surcharge. */
function FeesCard({ acc, hubraPercent }: { acc: Account; hubraPercent: number }) {
  const { t } = useT()
  const { notify } = useToast()
  const qc = useQueryClient()
  const [edits, setEdits] = useState<FeeEdits>({})
  const [saving, setSaving] = useState(false)
  const view: Account = { ...acc, ...edits }
  const dirty = Object.keys(edits).length > 0
  const save = async () => {
    setSaving(true)
    try {
      await saveFees(edits)
      await qc.invalidateQueries({ queryKey: QK.status })
      setEdits({})
      notify('success', t('payments.fees.saved'))
    } catch (err) {
      notify('error', errorText(err))
    } finally {
      setSaving(false)
    }
  }
  const total = priceFor(100, view, hubraPercent)
  return (
    <Paper withBorder p="lg">
      <Stack gap="sm">
        <Title order={4}>{t('payments.fees.title')}</Title>
        <Radio.Group
          value={view.passFees ? 'members' : 'club'}
          onChange={(v) => setEdits((e) => ({ ...e, passFees: v === 'members' }))}
        >
          <Stack gap="xs">
            <Radio value="club" label={t('payments.fees.club')} description={t('payments.fees.clubHint')} />
            <Radio value="members" label={t('payments.fees.members')} description={t('payments.fees.membersHint')} />
          </Stack>
        </Radio.Group>
        {view.passFees && (
          <>
            <Group gap="sm" align="flex-start" wrap="wrap">
              <NumberInput
                label={t('payments.fees.percent')}
                value={view.surchargePercent}
                onChange={(v) => setEdits((e) => ({ ...e, surchargePercent: Number(v) || 0 }))}
                min={0}
                max={10}
                step={0.1}
                decimalScale={2}
                w={200}
              />
              <NumberInput
                label={t('payments.fees.fixed')}
                value={view.surchargeFixed}
                onChange={(v) => setEdits((e) => ({ ...e, surchargeFixed: Number(v) || 0 }))}
                min={0}
                max={5}
                step={0.05}
                decimalScale={2}
                w={200}
              />
            </Group>
            <Text size="xs" c="dimmed">
              {t('payments.fees.rateHint')}
            </Text>
            <Text size="sm">
              {t('payments.fees.example', { amount: formatCHF(100), total: formatCHF(total) })}
            </Text>
            <Text size="xs" c="dimmed">
              {t('payments.fees.legal')}
            </Text>
          </>
        )}
        <Group>
          <Button onClick={save} loading={saving} disabled={!dirty}>
            {t('payments.fees.save')}
          </Button>
        </Group>
      </Stack>
    </Paper>
  )
}

/** Einstellungen for the club's Stripe account, and its online payments. */
export function PaymentsScreen() {
  const { t } = useT()
  const { notify } = useToast()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [params] = useSearchParams()
  const status = useQuery({ queryKey: QK.status, queryFn: getStatus })
  const checkouts = useQuery({
    queryKey: QK.checkouts,
    queryFn: listCheckouts,
    enabled: !!status.data?.canManage,
  })
  const [busy, setBusy] = useState<'connect' | 'refresh' | null>(null)
  const [confirmDisconnect, setConfirmDisconnect] = useState(false)

  const reload = () => qc.invalidateQueries({ queryKey: ['payments'] })

  const doRefresh = async (quiet = false) => {
    setBusy('refresh')
    try {
      await refresh()
      await reload()
      if (!quiet) notify('success', t('payments.checked'))
    } catch (err) {
      notify('error', errorText(err))
    } finally {
      setBusy(null)
    }
  }

  // Back from Stripe's setup pages: read the account again, once.
  const back = params.get('connected') || params.get('refresh')
  useEffect(() => {
    if (!back) return
    doRefresh(true).then(() => navigate('/app/payments', { replace: true }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [back])

  const doConnect = async () => {
    setBusy('connect')
    try {
      const { url } = await connect()
      window.location.assign(url)
    } catch (err) {
      notify('error', errorText(err))
      setBusy(null)
    }
  }

  const doDisconnect = async () => {
    try {
      await disconnect()
      await reload()
      notify('success', t('payments.disconnected'))
    } catch (err) {
      notify('error', errorText(err))
    }
    setConfirmDisconnect(false)
  }

  if (status.isLoading) return <LoadingSpinner />
  if (status.isError || !status.data) {
    return <ErrorBanner message={t('payments.loadFailed')} onRetry={() => status.refetch()} />
  }
  const s = status.data
  const acc: Account | null | undefined = s.account

  return (
    <>
      <PageHead title={t('payments.title')} desc={t('payments.desc')} />
      <Stack gap="md">
        {!s.platform && (
          <Alert color="yellow" icon={<IconAlertTriangle size={18} />}>
            {t('payments.noPlatform')}
          </Alert>
        )}

        <Paper withBorder p="lg">
          <Group justify="space-between" align="flex-start" wrap="wrap" gap="md">
            <Stack gap={6}>
              <Group gap="xs">
                <IconBrandStripe size={22} />
                <Title order={3}>{acc?.name || t('payments.stripeAccount')}</Title>
                {s.testMode && (
                  <Badge color="orange" variant="light">
                    {t('payments.testMode')}
                  </Badge>
                )}
              </Group>
              {!acc && <Text c="dimmed">{t('payments.notConnected')}</Text>}
              {acc && (
                <>
                  <Text size="sm" c="dimmed">
                    {acc.chargesEnabled
                      ? t('payments.readyText')
                      : acc.detailsSubmitted
                        ? t('payments.reviewText')
                        : t('payments.setupText')}
                  </Text>
                  <Group gap={6}>
                    <Flag on={acc.chargesEnabled} label={t('payments.flag.charges')} />
                    <Flag on={acc.card} label={t('payments.flag.card')} />
                    <Flag on={acc.twint} label={t('payments.flag.twint')} />
                  </Group>
                  {acc.chargesEnabled && !acc.twint && (
                    <Text size="xs" c="dimmed">
                      {t('payments.twintHint')}
                    </Text>
                  )}
                  <Text size="xs" c="dimmed">
                    {acc.id}
                    {acc.checkedAt ? ` · ${t('payments.checkedAt', { at: formatDateTime(acc.checkedAt) })}` : ''}
                  </Text>
                </>
              )}
              {!!s.feePercent && (
                <Text size="xs" c="dimmed">
                  {t('payments.fee', { percent: String(s.feePercent) })}
                </Text>
              )}
            </Stack>
            <Group gap="xs">
              {acc && (
                <Button
                  variant="default"
                  leftSection={<IconRefresh size={16} />}
                  loading={busy === 'refresh'}
                  onClick={() => doRefresh()}
                >
                  {t('payments.check')}
                </Button>
              )}
              {s.platform && (!acc || !acc.chargesEnabled) && (
                <Button loading={busy === 'connect'} onClick={doConnect}>
                  {acc ? t('payments.continueSetup') : t('payments.connect')}
                </Button>
              )}
              {acc && (
                <Button variant="subtle" color="red" onClick={() => setConfirmDisconnect(true)}>
                  {t('payments.disconnect')}
                </Button>
              )}
            </Group>
          </Group>
        </Paper>

        {acc && <FeesCard acc={acc} hubraPercent={s.feePercent ?? 0} />}

        <Paper withBorder>
          <Group p="md" style={{ borderBottom: '1px solid var(--hb-border)' }}>
            <Text fw={700}>{t('payments.listTitle')}</Text>
          </Group>
          {checkouts.isLoading ? (
            <LoadingSpinner />
          ) : !checkouts.data?.length ? (
            <EmptyState title={t('payments.emptyTitle')} description={t('payments.emptyDesc')} />
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <Table className="responsive-table">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t('payments.col.date')}</Table.Th>
                    <Table.Th>{t('payments.col.invoice')}</Table.Th>
                    <Table.Th>{t('payments.col.member')}</Table.Th>
                    <Table.Th>{t('payments.col.method')}</Table.Th>
                    <Table.Th>{t('payments.col.status')}</Table.Th>
                    <Table.Th style={{ textAlign: 'right' }}>{t('payments.col.amount')}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {checkouts.data.map((c) => (
                    <Table.Tr key={c.id}>
                      <Table.Td data-label={t('payments.col.date')}>
                        {formatDateTime(c.paidAt ?? c.createdAt ?? '')}
                      </Table.Td>
                      <Table.Td data-label={t('payments.col.invoice')}>
                        {c.invoiceId ? (
                          <Text
                            component="a"
                            href="#"
                            size="sm"
                            c="var(--mantine-color-acc-text)"
                            onClick={(e: React.MouseEvent) => {
                              e.preventDefault()
                              navigate(`/app/finance/invoices/${c.invoiceId}`)
                            }}
                          >
                            {c.invoiceId}
                          </Text>
                        ) : (
                          '–'
                        )}
                      </Table.Td>
                      <Table.Td data-label={t('payments.col.member')}>{c.memberName ?? '–'}</Table.Td>
                      <Table.Td data-label={t('payments.col.method')}>
                        {c.method ? t(`payments.method.${c.method}`, { defaultValue: c.method }) : '–'}
                      </Table.Td>
                      <Table.Td data-label={t('payments.col.status')}>
                        <Badge
                          variant="light"
                          color={c.status === 'paid' ? 'green' : c.status === 'open' ? 'yellow' : 'gray'}
                        >
                          {t(`payments.state.${c.status}`)}
                        </Badge>
                      </Table.Td>
                      <Table.Td data-label={t('payments.col.amount')} style={{ textAlign: 'right' }} className="num">
                        CHF {formatCHF(c.amount)}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </div>
          )}
        </Paper>
      </Stack>

      <ConfirmModal
        open={confirmDisconnect}
        onClose={() => setConfirmDisconnect(false)}
        onConfirm={doDisconnect}
        title={t('payments.disconnectTitle')}
        body={t('payments.disconnectBody')}
      />
    </>
  )
}
