/** OPEN rec waiting for entry: limit price vs Paytm circuit band from security master. */

import {
  PENDING_OPEN_ORDER_ROW_TITLE,
  STALE_ORDER_ROW_TITLE,
} from './staleOrderWarning.js'

export const CIRCUIT_LIMIT_ROW_TITLE =
  'Order limit price is outside today’s circuit band (HIGH_REC_PRICE for BUY, LOW_REC_PRICE for SELL). appPaytm will clamp at place time.'

/** POS_HOLD_STATUS OPEN + REC_STATUS OPEN — not in position yet; broker will place open orders. */
export function isAwaitingOpenOrders(trade) {
  return trade.POS_HOLD_STATUS === 'OPEN' && trade.REC_STATUS === 'OPEN'
}

export function orderLimitPriceForCheck(trade) {
  const buySell = (trade.BUY_SELL || 'BUY').toUpperCase()
  const raw = buySell === 'BUY' ? trade.HIGH_REC_PRICE : trade.LOW_REC_PRICE
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
}

export function isLimitOutsideCircuit(limitPrice, buySell, upper, lower) {
  if (limitPrice == null || upper == null || lower == null) return false
  const side = (buySell || 'BUY').toUpperCase()
  if (side === 'BUY') {
    return limitPrice > upper || limitPrice < lower
  }
  return limitPrice < lower || limitPrice > upper
}

/**
 * @param {object} trade — API trade (includes CIRCUIT_UPPER / CIRCUIT_LOWER when known)
 * @param {object} [draft] — unsaved edits (HIGH_REC_PRICE / LOW_REC_PRICE)
 */
export function shouldWarnCircuitLimitBreach(trade, draft = {}) {
  if (!isAwaitingOpenOrders(trade)) return false
  const upper = trade.CIRCUIT_UPPER
  const lower = trade.CIRCUIT_LOWER
  if (upper == null || lower == null) return false
  const merged = { ...trade, ...draft }
  const limitPrice = orderLimitPriceForCheck(merged)
  if (limitPrice == null) return false
  return isLimitOutsideCircuit(limitPrice, merged.BUY_SELL, upper, lower)
}

export function bucketHasCircuitLimitBreach(bucket, getDraft) {
  return bucket.members.some((m) =>
    shouldWarnCircuitLimitBreach(m.trade, getDraft?.(m.id)),
  )
}

export function tradeRowClassName({ staleWarn, pendingOpenWarn, circuitWarn }) {
  const parts = []
  if (staleWarn) parts.push('row-stale-open-orders')
  if (pendingOpenWarn) parts.push('row-pending-open-orders')
  if (circuitWarn) parts.push('row-circuit-limit-breach')
  return parts.length ? parts.join(' ') : undefined
}

export function tradeRowTitle({ staleWarn, pendingOpenWarn, circuitWarn }) {
  const lines = []
  if (staleWarn) lines.push(STALE_ORDER_ROW_TITLE)
  if (pendingOpenWarn) lines.push(PENDING_OPEN_ORDER_ROW_TITLE)
  if (circuitWarn) lines.push(CIRCUIT_LIMIT_ROW_TITLE)
  return lines.length ? lines.join('\n') : undefined
}
