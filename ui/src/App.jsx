import { useCallback, useEffect, useMemo, useState } from 'react'

const LIST_COLS = [
  'MKT_SYMBOL',
  'SOURCE',
  'STRATEGY',
  'BUY_SELL',
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
  const [drafts, setDrafts] = useState({})
  const [banner, setBanner] = useState('')
  const [rowErrors, setRowErrors] = useState({})
  const [showCreate, setShowCreate] = useState(false)
  const [symbolHits, setSymbolHits] = useState([])
  const [createForm, setCreateForm] = useState({
    mode: 'buy_fresh',
    MKT_SYMBOL: '',
    STOCK: '',
    SOURCE: 'MANUAL',
    STRATEGY: 'CORE',
    PRODUCT: 'CASH',
    BUY_SELL: 'BUY',
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

  const closeCreate = useCallback(() => {
    setShowCreate(false)
    setSymbolHits([])
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

  const saveRow = async (id, trade) => {
    setBanner('')
    const draft = drafts[id] || {}
    const payload = {}
    for (const k of EDITABLE) {
      if (k in draft) payload[k] = Number(draft[k])
    }
    if (Object.keys(payload).length === 0) return
    try {
      await api(`/api/trades/${encodeURIComponent(id)}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      })
      await load()
    } catch (e) {
      setRowErrors((prev) => ({ ...prev, [id]: e.message }))
    }
  }

  const closeRow = async (id) => {
    if (!window.confirm('Close this trade? appPaytm will exit on next reconcile.')) return
    setBanner('')
    try {
      await api(`/api/trades/${encodeURIComponent(id)}/close`, { method: 'POST' })
      await load()
    } catch (e) {
      setRowErrors((prev) => ({ ...prev, [id]: e.message }))
    }
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

  const submitCreate = async (ev) => {
    ev.preventDefault()
    setBanner('')
    const body = {
      ...createForm,
      LOW_REC_PRICE: Number(createForm.LOW_REC_PRICE),
      HIGH_REC_PRICE: Number(createForm.HIGH_REC_PRICE),
      TARGET: Number(createForm.TARGET),
      STOP_LOSS: Number(createForm.STOP_LOSS),
      QTY: Number(createForm.QTY),
    }
    try {
      await api('/api/trades', { method: 'POST', body: JSON.stringify(body) })
      closeCreate()
      await load()
    } catch (e) {
      setBanner(e.message)
    }
  }

  const hasDraft = useMemo(
    () => (id) => drafts[id] && Object.keys(drafts[id]).length > 0,
    [drafts],
  )

  return (
    <div className="app">
      <header>
        <h1>Paytm Trade Manager</h1>
        <button type="button" onClick={() => setShowCreate(true)}>
          New trade
        </button>
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
        <button type="button" onClick={() => load().catch((e) => setBanner(e.message))}>
          Refresh
        </button>
      </section>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {LIST_COLS.map((c) => (
                <th key={c}>{c}</th>
              ))}
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ id, trade }) => {
              const row = getDraft(id, trade)
              return (
                <tr key={id}>
                  {LIST_COLS.map((col) => (
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
                      onClick={() => saveRow(id, trade)}
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      disabled={trade.REC_STATUS === 'CLOSE'}
                      onClick={() => closeRow(id)}
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
            <form className="modal-form" onSubmit={submitCreate}>
              <label>
                Mode
                <select
                  value={createForm.mode}
                  onChange={(e) => setCreateForm((f) => ({ ...f, mode: e.target.value }))}
                >
                  <option value="buy_fresh">Buy fresh</option>
                  <option value="already_held">Already held (exit only)</option>
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
    </div>
  )
}
