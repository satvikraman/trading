/** NSE cash session (IST): Mon–Fri 9:15–15:30; weekends always "outside". */

export const MARKET_OPEN_MINUTES = 9 * 60 + 15
export const MARKET_CLOSE_MINUTES = 15 * 60 + 30

export const STALE_ORDER_ROW_TITLE =
  'Stale OPEN order status in DB — fix before next session or appPaytm checkOpenOrders may fail.'

const IST = 'Asia/Kolkata'

export function getIstTimeParts(date = new Date()) {
  const hour = Number(
    new Intl.DateTimeFormat('en-GB', { timeZone: IST, hour: 'numeric', hour12: false }).format(date),
  )
  const minute = Number(
    new Intl.DateTimeFormat('en-GB', { timeZone: IST, minute: 'numeric' }).format(date),
  )
  const weekday = new Intl.DateTimeFormat('en-US', { timeZone: IST, weekday: 'short' }).format(date)
  return { minutes: hour * 60 + minute, weekday }
}

export function isOutsideTradingHours(date = new Date()) {
  const { minutes, weekday } = getIstTimeParts(date)
  if (weekday === 'Sat' || weekday === 'Sun') return true
  return minutes < MARKET_OPEN_MINUTES || minutes > MARKET_CLOSE_MINUTES
}

export function hasOpenOrderStatus(trade) {
  const isOpen = (order) => order?.ORDER_STATUS === 'OPEN'
  return (
    (trade.OPEN_ORDERS || []).some(isOpen) || (trade.CLOSE_ORDERS || []).some(isOpen)
  )
}

export function isActiveTrade(trade) {
  return trade.POS_HOLD_STATUS !== 'CLOSE'
}

/** Aligns with workflow.hasPendingOrders(..., filter='ALL') + active_only rows. */
export function shouldWarnStaleOpenOrders(trade, now = new Date()) {
  return isOutsideTradingHours(now) && isActiveTrade(trade) && hasOpenOrderStatus(trade)
}

export function bucketHasStaleOpenOrders(bucket, now = new Date()) {
  return bucket.members.some((m) => shouldWarnStaleOpenOrders(m.trade, now))
}
