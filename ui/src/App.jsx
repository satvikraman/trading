import { useCallback, useEffect, useMemo, useState } from 'react'
import ConfirmCommitModal from './ConfirmCommitModal.jsx'

const TRADE_COLS = [
  'MKT_SYMBOL',
  'SOURCE',
  'STRATEGY',
  'REC_DATE',
  'REC_TIME',
  'REC_STATUS',
  'POS_HOLD_STATUS',
  'LOW_REC_PRICE',
  'HIGH_REC_PRICE',
  'TARGET',
  'STOP_LOSS',
  'QTY',
  'POS_HOLD_QTY',
]

const EDITABLE = new Set(['QTY', 'LOW_REC_PRICE', 'HIGH_REC_PRICE', 'TARGET', 'STOP_LOSS'])

function summaryLine(label, value) {
  return { label, value: String(value ?? '') }
}

function patchSummaryLines(trade, draft) {
  const lines = [
    summaryLine('Operation', 'PATCH — update existing trade record'),
    summaryLine('Symbol', trade.MKT_SYMBOL),
    summaryLine('Source / Strategy', `${trade.SOURCE} / ${trade.STRATEGY}`),
    summaryLine('Recommendation', `${trade.REC_DATE} ${trade.REC_TIME}`),
  ]
  for (const k of EDITABLE) {
    if (k in draft) {
      lines.push(summaryLine(k, `${trade[k]} → ${draft[k]}`))
    }
  }
  return lines
}

function closeTradeSummaryLines(trade) {
  return [
    summaryLine('Operation', 'CLOSE — mark trade record closed (REC_STATUS = CLOSE)'),
    summaryLine('Symbol', trade.MKT_SYMBOL),
    summaryLine('Source / Strategy', `${trade.SOURCE} / ${trade.STRATEGY}`),
    summaryLine('Recommendation', `${trade.REC_DATE} ${trade.REC_TIME}`),
    summaryLine('POS_HOLD_QTY', trade.POS_HOLD_QTY),
  ]
}

function closePortfolioSummaryLines(bucket, toClose, acrossSource, acrossStrategy) {
  const label = [
    bucket.MKT_SYMBOL,
    !acrossSource && bucket.SOURCE ? bucket.SOURCE : null,
    !acrossStrategy && bucket.STRATEGY ? bucket.STRATEGY : null,
  ]
    .filter(Boolean)
    .join(' / ')
  const lines = [
    summaryLine('Operation', `CLOSE — mark ${toClose.length} trade record(s) closed`),
    summaryLine('Portfolio bucket', label),
    summaryLine('Bucket QTY (sum)', bucket.QTY),
    summaryLine('Bucket POS_HOLD_QTY (sum)', bucket.POS_HOLD_QTY),
  ]
  toClose.slice(0, 8).forEach((m, i) => {
    const t = m.trade
    lines.push(
      summaryLine(
        `Leg ${i + 1}`,
        `${t.SOURCE} / ${t.STRATEGY} — ${t.REC_DATE} ${t.REC_TIME} (hold ${t.POS_HOLD_QTY})`,
      ),
    )
  })
  if (toClose.length > 8) {
    lines.push(summaryLine('…', `and ${toClose.length - 8} more leg(s)`))
  }
  return lines
}

function renameSummaryLines(preview, form) {
  const lines = [
    summaryLine('Operation', 'RENAME — update MKT_SYMBOL on all matching trade rows'),
    summaryLine('From', preview.from_mkt_symbol),
    summaryLine('To', preview.to_mkt_symbol),
    summaryLine('Rows matched', preview.match_count),
    summaryLine('Will update', preview.would_update_count),
    summaryLine('Conflicts', preview.conflict_count),
  ]
  if (form.update_security_id && preview.security_id) {
    lines.push(summaryLine('SECURITY_ID', preview.security_id))
  }
  if (form.active_only) {
    lines.push(summaryLine('Scope', 'Active rows only (POS_HOLD_STATUS ≠ CLOSE)'))
  }
  preview.would_update.slice(0, 5).forEach((row, i) => {
    lines.push(
      summaryLine(
        `Row ${i + 1}`,
        `${row.SOURCE} / ${row.STRATEGY} — ${row.REC_DATE} ${row.REC_TIME} (hold ${row.POS_HOLD_QTY})`,
      ),
    )
  })
  if (preview.would_update_count > 5) {
    lines.push(summaryLine('…', `and ${preview.would_update_count - 5} more row(s)`))
  }
  return lines
}

function createTradeSummaryLines(form, body) {
  const modeNote =
    form.mode === 'buy_fresh'
      ? 'Buy fresh — bot may place buy orders when market is open'
      : 'Already held — records position only (no automatic buy from this row)'
  return [
    summaryLine('Operation', 'POST — insert new trade record'),
    summaryLine('Mode', modeNote),
    summaryLine('Symbol', body.MKT_SYMBOL),
    summaryLine('Source / Strategy', `${body.SOURCE} / ${body.STRATEGY}`),
    summaryLine('Recommendation', `${body.REC_DATE} ${body.REC_TIME}`),
    summaryLine('LOW_REC_PRICE', body.LOW_REC_PRICE),
    summaryLine('HIGH_REC_PRICE', body.HIGH_REC_PRICE),
    summaryLine('TARGET', body.TARGET),
    summaryLine('STOP_LOSS', body.STOP_LOSS),
    summaryLine('QTY', body.QTY),
  ]
}

function todayStr() {
  return new Date().toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).replace(/ /g, '-')
}

function formatErr(detail) {
  if (!detail) return 'Request failed'
  if (typeof detail === 'string') return detail
  if (detail.errors) {
    return detail.errors.map((e) => `${e.field}: ${e.message}`).join('; ')
  }
  return JSON.stringify(detail)
}

function portfolioGroupKey(trade, acrossSource, acrossStrategy) {
  const parts = [trade.MKT_SYMBOL ?? '']
  if (!acrossSource) parts.push(trade.SOURCE ?? '')
  if (!acrossStrategy) parts.push(trade.STRATEGY ?? '')
  return parts.join('|')
}

function portfolioColumns(acrossSource, acrossStrategy) {
  const cols = ['MKT_SYMBOL']
  if (!acrossSource) cols.push('SOURCE')
  if (!acrossStrategy) cols.push('STRATEGY')
  cols.push('POS_HOLD_QTY')
  return cols
}

function buildPortfolioBuckets(rows, acrossSource, acrossStrategy) {
  const map = new Map()
  for (const row of rows) {
    const { id, trade } = row
    const key = portfolioGroupKey(trade, acrossSource, acrossStrategy)
    if (!map.has(key)) {
      map.set(key, {
        key,
        MKT_SYMBOL: trade.MKT_SYMBOL,
        SOURCE: acrossSource ? undefined : trade.SOURCE,
        STRATEGY: acrossStrategy ? undefined : trade.STRATEGY,
        QTY: 0,
        POS_HOLD_QTY: 0,
        members: [],
      })
    }
    const bucket = map.get(key)
    bucket.QTY += Number(trade.QTY) || 0
    bucket.POS_HOLD_QTY += Number(trade.POS_HOLD_QTY) || 0
    bucket.members.push({ id, trade })
  }
  return [...map.values()].sort((a, b) =>
    String(a.MKT_SYMBOL).localeCompare(String(b.MKT_SYMBOL)),
  )
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(formatErr(body.detail ?? body))
  return body
}

export default function App() {
  const [rows, setRows] = useState([])
  const [sources, setSources] = useState([])
  const [filters, setFilters] = useState({
    source: '',
    rec_status: '',
    pos_hold_status: '',
    mkt_symbol: '',
    active_only: true,
  })
  const [portfolioView, setPortfolioView] = useState(false)
  const [accumulateAcrossSource, setAccumulateAcrossSource] = useState(true)
  const [accumulateAcrossStrategy, setAccumulateAcrossStrategy] = useState(true)
  const [drafts, setDrafts] = useState({})
  const [banner, setBanner] = useState('')
  const [rowErrors, setRowErrors] = useState({})
  const [showCreate, setShowCreate] = useState(false)
  const [showRename, setShowRename] = useState(false)
  const [confirmPending, setConfirmPending] = useState(null)
  const [symbolHits, setSymbolHits] = useState([])
  const [renameToHits, setRenameToHits] = useState([])
  const [renameForm, setRenameForm] = useState({
    from_mkt_symbol: '',
    to_mkt_symbol: '',
    update_security_id: true,
    active_only: false,
  })
  const [createForm, setCreateForm] = useState({
    mode: 'buy_fresh',
    MKT_SYMBOL: '',
    STOCK: '',
    SOURCE: 'MANUAL',
    STRATEGY: 'CORE',
    PRODUCT: 'CASH',
    MKT: 'NSE',
    REC_DATE: todayStr(),
    REC_TIME: 'xx:xx',
    EXP_DATE: '',
    LOW_REC_PRICE: '',
    HIGH_REC_PRICE: '',
    TARGET: '',
    STOP_LOSS: '',
    QTY: '',
    SECURITY_ID: '',
    ICICI_SYMBOL: '',
  })

  const load = useCallback(async () => {
    setBanner('')
    const params = new URLSearchParams()
    if (filters.source) params.set('source', filters.source)
    if (filters.rec_status) params.set('rec_status', filters.rec_status)
    if (filters.pos_hold_status) params.set('pos_hold_status', filters.pos_hold_status)
    if (filters.mkt_symbol) params.set('mkt_symbol', filters.mkt_symbol)
    if (filters.active_only) params.set('active_only', 'true')
    const data = await api(`/api/trades?${params}`)
    setRows(data)
    setDrafts({})
    setRowErrors({})
  }, [filters])

  useEffect(() => {
    api('/api/sources')
      .then(setSources)
      .catch((e) => setBanner(e.message))
  }, [])

  useEffect(() => {
    load().catch((e) => setBanner(e.message))
  }, [load])

  const portfolioBuckets = useMemo(
    () => buildPortfolioBuckets(rows, accumulateAcrossSource, accumulateAcrossStrategy),
    [rows, accumulateAcrossSource, accumulateAcrossStrategy],
  )

  const tableColumns = useMemo(() => {
    if (!portfolioView) return TRADE_COLS
    return portfolioColumns(accumulateAcrossSource, accumulateAcrossStrategy)
  }, [portfolioView, accumulateAcrossSource, accumulateAcrossStrategy])

  const closeCreate = useCallback(() => {
    setShowCreate(false)
    setSymbolHits([])
  }, [])

  const closeRename = useCallback(() => {
    setShowRename(false)
    setRenameToHits([])
  }, [])

  useEffect(() => {
    if (!showCreate) return
    const onKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        closeCreate()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [showCreate, closeCreate])

  const onFilter = (key, value) => setFilters((f) => ({ ...f, [key]: value }))

  const getDraft = (id, trade) => {
    const d = drafts[id]
    if (!d) return trade
    return { ...trade, ...d }
  }

  const setDraftField = (id, trade, field, value) => {
    setDrafts((prev) => ({
      ...prev,
      [id]: { ...(prev[id] || {}), [field]: value },
    }))
    setRowErrors((prev) => {
      const next = { ...prev }
      delete next[id]
      return next
    })
  }

  const requestSaveRow = (id, trade) => {
    const draft = drafts[id] || {}
    const payload = {}
    for (const k of EDITABLE) {
      if (k in draft) payload[k] = Number(draft[k])
    }
    if (Object.keys(payload).length === 0) return
    setConfirmPending({
      title: 'Confirm save to database',
      actionLabel: 'Save changes',
      lines: patchSummaryLines(trade, draft),
      onConfirm: async () => {
        setBanner('')
        await api(`/api/trades/${encodeURIComponent(id)}`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        })
        await load()
      },
    })
  }

  const requestCloseRow = (id, trade) => {
    setConfirmPending({
      title: 'Confirm close trade',
      actionLabel: 'Close trade',
      lines: closeTradeSummaryLines(trade),
      onConfirm: async () => {
        setBanner('')
        await api(`/api/trades/${encodeURIComponent(id)}/close`, { method: 'POST' })
        await load()
      },
    })
  }

  const requestClosePortfolioBucket = (bucket) => {
    const toClose = bucket.members.filter((m) => m.trade.REC_STATUS !== 'CLOSE')
    if (toClose.length === 0) return
    setConfirmPending({
      title: 'Confirm close portfolio position',
      actionLabel: `Close ${toClose.length} leg(s)`,
      lines: closePortfolioSummaryLines(
        bucket,
        toClose,
        accumulateAcrossSource,
        accumulateAcrossStrategy,
      ),
      onConfirm: async () => {
        setBanner('')
        const errors = []
        for (const { id } of toClose) {
          try {
            await api(`/api/trades/${encodeURIComponent(id)}/close`, { method: 'POST' })
          } catch (e) {
            errors.push(e.message)
          }
        }
        await load()
        if (errors.length) {
          setRowErrors((prev) => ({ ...prev, [bucket.key]: errors.join('; ') }))
          throw new Error(errors.join('; '))
        }
      },
    })
  }

  const lookupSymbol = async (q) => {
    setCreateForm((f) => ({ ...f, MKT_SYMBOL: q }))
    if (q.length < 2) {
      setSymbolHits([])
      return
    }
    try {
      const hits = await api(`/api/symbols/lookup?q=${encodeURIComponent(q)}`)
      setSymbolHits(hits)
    } catch {
      setSymbolHits([])
    }
  }

  const pickSymbol = (hit) => {
    setCreateForm((f) => ({
      ...f,
      MKT_SYMBOL: hit.MKT_SYMBOL,
      STOCK: hit.STOCK || hit.MKT_SYMBOL,
      SECURITY_ID: hit.SECURITY_ID,
      ICICI_SYMBOL: hit.ICICI_SYMBOL,
      MKT: hit.MKT || 'NSE',
    }))
    setSymbolHits([])
  }

  const lookupRenameTo = async (q) => {
    setRenameForm((f) => ({ ...f, to_mkt_symbol: q }))
    if (q.length < 2) {
      setRenameToHits([])
      return
    }
    try {
      const hits = await api(`/api/symbols/lookup?q=${encodeURIComponent(q)}`)
      setRenameToHits(hits)
    } catch {
      setRenameToHits([])
    }
  }

  const pickRenameTo = (hit) => {
    setRenameForm((f) => ({ ...f, to_mkt_symbol: hit.MKT_SYMBOL }))
    setRenameToHits([])
  }

  const requestRenameSymbol = async (ev) => {
    ev.preventDefault()
    setBanner('')
    const params = new URLSearchParams({
      from_mkt_symbol: renameForm.from_mkt_symbol.trim(),
      to_mkt_symbol: renameForm.to_mkt_symbol.trim(),
      update_security_id: String(renameForm.update_security_id),
      active_only: String(renameForm.active_only),
    })
    let preview
    try {
      preview = await api(`/api/symbols/rename/preview?${params}`)
    } catch (e) {
      setBanner(e.message)
      return
    }
    if (preview.conflict_count > 0) {
      setBanner(
        `${preview.conflict_count} row(s) would conflict with an existing ${preview.to_mkt_symbol} trade. Resolve duplicates first.`,
      )
      return
    }
    if (preview.would_update_count === 0) {
      setBanner(`No rows found with symbol ${preview.from_mkt_symbol}`)
      return
    }
    setConfirmPending({
      title: 'Confirm symbol rename',
      actionLabel: `Rename ${preview.would_update_count} row(s)`,
      lines: renameSummaryLines(preview, renameForm),
      onConfirm: async () => {
        setBanner('')
        await api('/api/symbols/rename', {
          method: 'POST',
          body: JSON.stringify({
            from_mkt_symbol: renameForm.from_mkt_symbol.trim(),
            to_mkt_symbol: renameForm.to_mkt_symbol.trim(),
            update_security_id: renameForm.update_security_id,
            active_only: renameForm.active_only,
          }),
        })
        closeRename()
        await load()
      },
    })
  }

  const requestCreateTrade = (ev) => {
    ev.preventDefault()
    const form = ev.currentTarget
    if (!form.reportValidity()) return
    const body = {
      ...createForm,
      BUY_SELL: 'BUY',
      LOW_REC_PRICE: Number(createForm.LOW_REC_PRICE),
      HIGH_REC_PRICE: Number(createForm.HIGH_REC_PRICE),
      TARGET: Number(createForm.TARGET),
      STOP_LOSS: Number(createForm.STOP_LOSS),
      QTY: Number(createForm.QTY),
    }
    setConfirmPending({
      title: 'Confirm new trade',
      actionLabel: 'Create trade',
      lines: createTradeSummaryLines(createForm, body),
      onConfirm: async () => {
        setBanner('')
        await api('/api/trades', { method: 'POST', body: JSON.stringify(body) })
        closeCreate()
        await load()
      },
    })
  }

  const hasDraft = useMemo(
    () => (id) => drafts[id] && Object.keys(drafts[id]).length > 0,
    [drafts],
  )

  const portfolioCloseDisabled = (bucket) =>
    !bucket.members.some((m) => m.trade.REC_STATUS !== 'CLOSE')

  return (
    <div className="app">
      <header>
        <h1>Paytm Trade Manager</h1>
        <div className="header-actions">
          <button type="button" className="btn btn-secondary" onClick={() => setShowRename(true)}>
            Rename symbol
          </button>
          <button type="button" onClick={() => setShowCreate(true)}>
            New trade
          </button>
        </div>
      </header>

      {banner && <div className="banner-error">{banner}</div>}

      <section className="filters">
        <label>
          Source
          <select value={filters.source} onChange={(e) => onFilter('source', e.target.value)}>
            <option value="">All</option>
            {sources.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label>
          REC_STATUS
          <select value={filters.rec_status} onChange={(e) => onFilter('rec_status', e.target.value)}>
            <option value="">All</option>
            <option value="OPEN">OPEN</option>
            <option value="PARTIAL_CLOSE">PARTIAL_CLOSE</option>
            <option value="CLOSE">CLOSE</option>
          </select>
        </label>
        <label>
          POS_HOLD_STATUS
          <select
            value={filters.pos_hold_status}
            onChange={(e) => onFilter('pos_hold_status', e.target.value)}
          >
            <option value="">All</option>
            <option value="OPEN">OPEN</option>
            <option value="POSITION">POSITION</option>
            <option value="CLOSE">CLOSE</option>
          </select>
        </label>
        <label>
          Symbol
          <input
            value={filters.mkt_symbol}
            onChange={(e) => onFilter('mkt_symbol', e.target.value)}
            placeholder="filter"
          />
        </label>
        <label>
          <span>Active only</span>
          <input
            type="checkbox"
            checked={filters.active_only}
            onChange={(e) => onFilter('active_only', e.target.checked)}
          />
        </label>
        <label>
          <span>Portfolio view</span>
          <input
            type="checkbox"
            checked={portfolioView}
            onChange={(e) => setPortfolioView(e.target.checked)}
          />
        </label>
        {portfolioView && (
          <div
            className="portfolio-grouping"
            role="group"
            aria-labelledby="portfolio-grouping-label"
          >
            <div id="portfolio-grouping-label" className="portfolio-grouping-title">
              Roll up
            </div>
            <div className="portfolio-grouping-toggles">
              <label className="toggle-item" title="When on, sums all sources for each symbol">
                <span className="toggle-item-label">Source</span>
                <span className="toggle-switch">
                  <input
                    type="checkbox"
                    role="switch"
                    checked={accumulateAcrossSource}
                    onChange={(e) => setAccumulateAcrossSource(e.target.checked)}
                  />
                  <span className="toggle-track" aria-hidden="true" />
                </span>
              </label>
              <label className="toggle-item" title="When on, sums all strategies for each symbol">
                <span className="toggle-item-label">Strategy</span>
                <span className="toggle-switch">
                  <input
                    type="checkbox"
                    role="switch"
                    checked={accumulateAcrossStrategy}
                    onChange={(e) => setAccumulateAcrossStrategy(e.target.checked)}
                  />
                  <span className="toggle-track" aria-hidden="true" />
                </span>
              </label>
            </div>
          </div>
        )}
        <button type="button" onClick={() => load().catch((e) => setBanner(e.message))}>
          Refresh
        </button>
      </section>

      {portfolioView && (
        <p className="portfolio-hint">
          Portfolio view: quantities are summed; only Close is available. Use trade view to edit legs.
          {!accumulateAcrossSource || !accumulateAcrossStrategy ? (
            <>
              {' '}
              Grouping:
              {!accumulateAcrossSource && !accumulateAcrossStrategy
                ? ' symbol + source + strategy'
                : !accumulateAcrossSource
                  ? ' symbol + source'
                  : ' symbol + strategy'}
              .
            </>
          ) : (
            <> Grouping: symbol only (all sources and strategies).</>
          )}
        </p>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {tableColumns.map((c) => (
                <th key={c}>{c}</th>
              ))}
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {portfolioView
              ? portfolioBuckets.map((bucket) => (
                  <tr key={bucket.key}>
                    {tableColumns.map((col) => (
                      <td key={col} className="readonly">
                        {bucket[col] ?? ''}
                      </td>
                    ))}
                    <td className="actions">
                      <button
                        type="button"
                        disabled={portfolioCloseDisabled(bucket)}
                        onClick={() => requestClosePortfolioBucket(bucket)}
                      >
                        Close
                      </button>
                      {rowErrors[bucket.key] && (
                        <div className="error">{rowErrors[bucket.key]}</div>
                      )}
                    </td>
                  </tr>
                ))
              : rows.map(({ id, trade }) => {
                  const row = getDraft(id, trade)
                  return (
                    <tr key={id}>
                      {TRADE_COLS.map((col) => (
                        <td key={col} className={EDITABLE.has(col) ? '' : 'readonly'}>
                          {EDITABLE.has(col) ? (
                            <input
                              value={row[col] ?? ''}
                              onChange={(e) => setDraftField(id, trade, col, e.target.value)}
                            />
                          ) : (
                            row[col]
                          )}
                        </td>
                      ))}
                      <td className="actions">
                        <button
                          type="button"
                          disabled={!hasDraft(id)}
                          onClick={() => requestSaveRow(id, trade)}
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          disabled={trade.REC_STATUS === 'CLOSE'}
                          onClick={() => requestCloseRow(id, trade)}
                        >
                          Close
                        </button>
                        {rowErrors[id] && <div className="error">{rowErrors[id]}</div>}
                      </td>
                    </tr>
                  )
                })}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <div className="modal-backdrop" onClick={closeCreate}>
          <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="New trade">
            <form className="modal-form" onSubmit={requestCreateTrade}>
              <label>
                Mode
                <select
                  value={createForm.mode}
                  onChange={(e) => setCreateForm((f) => ({ ...f, mode: e.target.value }))}
                >
                  <option value="buy_fresh">Buy fresh</option>
                  <option value="already_held">Already held (offline / exit only)</option>
                </select>
              </label>
              <label>
                Market symbol
                <input
                  value={createForm.MKT_SYMBOL}
                  onChange={(e) => lookupSymbol(e.target.value)}
                  placeholder="e.g. RELIANCE"
                  autoComplete="off"
                  required
                />
                {symbolHits.length > 0 && (
                  <ul className="symbol-suggestions">
                    {symbolHits.map((h) => (
                      <li key={h.MKT_SYMBOL}>
                        <button type="button" onClick={() => pickSymbol(h)}>
                          <span className="sym-name">{h.MKT_SYMBOL}</span>
                          <span className="sym-meta">ID {h.SECURITY_ID}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </label>
              <div className="row">
                <label>
                  Source
                  <input
                    value={createForm.SOURCE}
                    onChange={(e) => setCreateForm((f) => ({ ...f, SOURCE: e.target.value }))}
                  />
                </label>
                <label>
                  Strategy
                  <input
                    value={createForm.STRATEGY}
                    onChange={(e) => setCreateForm((f) => ({ ...f, STRATEGY: e.target.value }))}
                  />
                </label>
              </div>
              <div className="row">
                <label>
                  Rec date
                  <input
                    value={createForm.REC_DATE}
                    onChange={(e) => setCreateForm((f) => ({ ...f, REC_DATE: e.target.value }))}
                  />
                </label>
                <label>
                  Rec time
                  <input
                    value={createForm.REC_TIME}
                    onChange={(e) => setCreateForm((f) => ({ ...f, REC_TIME: e.target.value }))}
                  />
                </label>
              </div>
              <div className="row">
                <label>
                  Low price
                  <input
                    type="number"
                    step="any"
                    required
                    value={createForm.LOW_REC_PRICE}
                    onChange={(e) =>
                      setCreateForm((f) => ({ ...f, LOW_REC_PRICE: e.target.value }))
                    }
                  />
                </label>
                <label>
                  High price
                  <input
                    type="number"
                    step="any"
                    required
                    value={createForm.HIGH_REC_PRICE}
                    onChange={(e) =>
                      setCreateForm((f) => ({ ...f, HIGH_REC_PRICE: e.target.value }))
                    }
                  />
                </label>
              </div>
              <div className="row">
                <label>
                  Target
                  <input
                    type="number"
                    step="any"
                    required
                    value={createForm.TARGET}
                    onChange={(e) => setCreateForm((f) => ({ ...f, TARGET: e.target.value }))}
                  />
                </label>
                <label>
                  Stop loss
                  <input
                    type="number"
                    step="any"
                    required
                    value={createForm.STOP_LOSS}
                    onChange={(e) => setCreateForm((f) => ({ ...f, STOP_LOSS: e.target.value }))}
                  />
                </label>
              </div>
              <label className="field-qty">
                Quantity
                <input
                  type="number"
                  required
                  min="1"
                  value={createForm.QTY}
                  onChange={(e) => setCreateForm((f) => ({ ...f, QTY: e.target.value }))}
                />
              </label>
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={closeCreate}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Create trade
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showRename && (
        <div className="modal-backdrop" onClick={closeRename}>
          <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Rename symbol">
            <form className="modal-form" onSubmit={requestRenameSymbol}>
              <h2 className="modal-title">Rename symbol</h2>
              <p className="modal-hint">
                Updates MKT_SYMBOL on all matching rows in the database (not per-row edit). Use when
                the exchange ticker changed (e.g. GOLDSHARE → GOLDBETA).
              </p>
              <label>
                From (current symbol in DB)
                <input
                  value={renameForm.from_mkt_symbol}
                  onChange={(e) =>
                    setRenameForm((f) => ({ ...f, from_mkt_symbol: e.target.value.toUpperCase() }))
                  }
                  placeholder="e.g. GOLDSHARE"
                  autoComplete="off"
                  required
                />
              </label>
              <label>
                To (new NSE symbol)
                <input
                  value={renameForm.to_mkt_symbol}
                  onChange={(e) => lookupRenameTo(e.target.value.toUpperCase())}
                  placeholder="e.g. GOLDBETA"
                  autoComplete="off"
                  required
                />
                {renameToHits.length > 0 && (
                  <ul className="symbol-suggestions">
                    {renameToHits.map((h) => (
                      <li key={h.MKT_SYMBOL}>
                        <button type="button" onClick={() => pickRenameTo(h)}>
                          <span className="sym-name">{h.MKT_SYMBOL}</span>
                          <span className="sym-meta">ID {h.SECURITY_ID}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={renameForm.update_security_id}
                  onChange={(e) =>
                    setRenameForm((f) => ({ ...f, update_security_id: e.target.checked }))
                  }
                />
                Update SECURITY_ID / ICICI_SYMBOL from NSE scrip master
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={renameForm.active_only}
                  onChange={(e) => setRenameForm((f) => ({ ...f, active_only: e.target.checked }))}
                />
                Active rows only (skip CLOSED positions)
              </label>
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={closeRename}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Preview &amp; confirm
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <ConfirmCommitModal pending={confirmPending} onCancel={() => setConfirmPending(null)} />
    </div>
  )
}