// Lightweight, dependency-free SVG visualizations for the Team & League
// Performance stat cards (TODO #41–#50). Each chart consumes the raw rows
// returned by the Sleeper stats API.

type Row = Record<string, unknown>

// A small categorical palette that reads well on light and dark themes.
const PALETTE = [
  "#2563eb",
  "#dc2626",
  "#16a34a",
  "#d97706",
  "#9333ea",
  "#0891b2",
  "#db2777",
  "#65a30d",
  "#ea580c",
  "#4f46e5",
  "#0d9488",
  "#b91c1c",
]

function colorFor(index: number): string {
  return PALETTE[index % PALETTE.length]
}

interface SeriesPoint {
  week: number
  [key: string]: number
}

function getSeries(row: Row): SeriesPoint[] {
  const series = row.series
  return Array.isArray(series) ? (series as SeriesPoint[]) : []
}

function teamName(row: Row): string {
  return (row.display_name as string) ?? `Team ${row.roster_id}`
}

interface LegendProps {
  rows: Row[]
}

function Legend({ rows }: LegendProps) {
  return (
    <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1">
      {rows.map((row, i) => (
        <div
          key={(row.roster_id as number) ?? i}
          className="flex items-center gap-1.5"
        >
          <span
            className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
            style={{ backgroundColor: colorFor(i) }}
          />
          <span className="truncate text-[11px] font-medium text-muted-foreground">
            {teamName(row)}
          </span>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// #41 Power Ranking Trend — rank movement week over week (lower rank = better)
// ---------------------------------------------------------------------------

export function RankTrendChart({ rows }: { rows: Row[] }) {
  const width = 520
  const height = 240
  const padding = { top: 16, right: 16, bottom: 28, left: 32 }
  const weeks = getSeries(rows[0]).map((p) => p.week)
  if (weeks.length === 0) return <EmptyChart />
  const nTeams = rows.length
  const minWeek = Math.min(...weeks)
  const maxWeek = Math.max(...weeks)

  const x = (week: number) =>
    padding.left +
    ((week - minWeek) / Math.max(maxWeek - minWeek, 1)) *
      (width - padding.left - padding.right)
  // Rank 1 sits at the top.
  const y = (rank: number) =>
    padding.top +
    ((rank - 1) / Math.max(nTeams - 1, 1)) *
      (height - padding.top - padding.bottom)

  return (
    <div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        role="img"
        aria-label="Power ranking trend lines"
      >
        {Array.from({ length: nTeams }, (_, i) => i + 1).map((rank) => (
          <line
            key={rank}
            x1={padding.left}
            x2={width - padding.right}
            y1={y(rank)}
            y2={y(rank)}
            className="stroke-border"
            strokeWidth={0.5}
          />
        ))}
        {rows.map((row, i) => {
          const series = getSeries(row)
          const d = series
            .map(
              (p, j) =>
                `${j === 0 ? "M" : "L"} ${x(p.week).toFixed(1)} ${y(p.rank).toFixed(1)}`,
            )
            .join(" ")
          return (
            <g key={(row.roster_id as number) ?? i}>
              <path
                d={d}
                fill="none"
                stroke={colorFor(i)}
                strokeWidth={2}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
              {series.map((p, j) => (
                <circle
                  key={j}
                  cx={x(p.week)}
                  cy={y(p.rank)}
                  r={2.5}
                  fill={colorFor(i)}
                />
              ))}
            </g>
          )
        })}
        {weeks.map((w) => (
          <text
            key={w}
            x={x(w)}
            y={height - 8}
            textAnchor="middle"
            className="fill-muted-foreground text-[9px]"
          >
            W{w}
          </text>
        ))}
      </svg>
      <Legend rows={rows} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// #43 Points For / Against — scatter with quadrant labeling
// ---------------------------------------------------------------------------

export function ScatterChart({ rows }: { rows: Row[] }) {
  const width = 520
  const height = 280
  const padding = { top: 16, right: 16, bottom: 32, left: 44 }
  if (rows.length === 0) return <EmptyChart />

  const pf = rows.map((r) => r.points_for as number)
  const pa = rows.map((r) => r.points_against as number)
  const minPf = Math.min(...pf)
  const maxPf = Math.max(...pf)
  const minPa = Math.min(...pa)
  const maxPa = Math.max(...pa)
  const padX = (maxPf - minPf || 1) * 0.1
  const padY = (maxPa - minPa || 1) * 0.1
  const medianFor = rows[0]?.median_for as number
  const medianAgainst = rows[0]?.median_against as number

  const x = (v: number) =>
    padding.left +
    ((v - (minPf - padX)) / (maxPf - minPf + 2 * padX || 1)) *
      (width - padding.left - padding.right)
  // Invert Y so fewer points-against (better) is higher.
  const y = (v: number) =>
    padding.top +
    (1 - (v - (minPa - padY)) / (maxPa - minPa + 2 * padY || 1)) *
      (height - padding.top - padding.bottom)

  return (
    <div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        role="img"
        aria-label="Points for versus points against scatter plot"
      >
        {/* Quadrant divider lines at the league medians */}
        {Number.isFinite(medianFor) && (
          <line
            x1={x(medianFor)}
            x2={x(medianFor)}
            y1={padding.top}
            y2={height - padding.bottom}
            className="stroke-border"
            strokeDasharray="3 3"
          />
        )}
        {Number.isFinite(medianAgainst) && (
          <line
            x1={padding.left}
            x2={width - padding.right}
            y1={y(medianAgainst)}
            y2={y(medianAgainst)}
            className="stroke-border"
            strokeDasharray="3 3"
          />
        )}
        {rows.map((row, i) => (
          <g key={(row.roster_id as number) ?? i}>
            <circle
              cx={x(row.points_for as number)}
              cy={y(row.points_against as number)}
              r={5}
              fill={colorFor(i)}
              fillOpacity={0.85}
            />
            <text
              x={x(row.points_for as number)}
              y={y(row.points_against as number) - 8}
              textAnchor="middle"
              className="fill-foreground text-[9px] font-semibold"
            >
              {teamName(row)}
            </text>
          </g>
        ))}
        <text
          x={(width + padding.left) / 2}
          y={height - 6}
          textAnchor="middle"
          className="fill-muted-foreground text-[10px]"
        >
          Points For →
        </text>
        <text
          x={12}
          y={(height - padding.bottom + padding.top) / 2}
          textAnchor="middle"
          transform={`rotate(-90 12 ${(height - padding.bottom + padding.top) / 2})`}
          className="fill-muted-foreground text-[10px]"
        >
          ← Points Against
        </text>
      </svg>
    </div>
  )
}

// ---------------------------------------------------------------------------
// #49 Margin of Victory — league-wide distribution histogram
// ---------------------------------------------------------------------------

export function MarginHistogram({ rows }: { rows: Row[] }) {
  const width = 520
  const height = 220
  const padding = { top: 16, right: 16, bottom: 32, left: 32 }

  const margins: number[] = []
  for (const row of rows) {
    const m = row.margins
    if (Array.isArray(m)) {
      for (const v of m as number[]) margins.push(v)
    }
  }
  if (margins.length === 0) return <EmptyChart />

  // Build symmetric buckets of 10 points centered on zero.
  const maxAbs = Math.max(...margins.map((m) => Math.abs(m)), 10)
  const bucketSize = 10
  const nBuckets = Math.ceil(maxAbs / bucketSize)
  const buckets: { label: string; count: number; center: number }[] = []
  for (let b = -nBuckets; b < nBuckets; b++) {
    const lo = b * bucketSize
    const hi = lo + bucketSize
    const count = margins.filter((m) => m >= lo && m < hi).length
    buckets.push({ label: `${lo}`, count, center: lo + bucketSize / 2 })
  }
  const maxCount = Math.max(...buckets.map((b) => b.count), 1)
  const chartW = width - padding.left - padding.right
  const chartH = height - padding.top - padding.bottom
  const barW = chartW / buckets.length

  return (
    <div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        role="img"
        aria-label="Distribution of weekly margins of victory"
      >
        {buckets.map((bucket, i) => {
          const h = (bucket.count / maxCount) * chartH
          const xPos = padding.left + i * barW
          const isClose = Math.abs(bucket.center) <= bucketSize
          return (
            <g key={i}>
              <rect
                x={xPos + 1}
                y={padding.top + chartH - h}
                width={Math.max(barW - 2, 1)}
                height={h}
                rx={1.5}
                fill={
                  isClose
                    ? "#16a34a"
                    : bucket.center < 0
                      ? "#dc2626"
                      : "#2563eb"
                }
                fillOpacity={0.8}
              />
              {bucket.count > 0 && (
                <text
                  x={xPos + barW / 2}
                  y={padding.top + chartH - h - 3}
                  textAnchor="middle"
                  className="fill-muted-foreground text-[8px]"
                >
                  {bucket.count}
                </text>
              )}
              {i % 2 === 0 && (
                <text
                  x={xPos + barW / 2}
                  y={height - 8}
                  textAnchor="middle"
                  className="fill-muted-foreground text-[8px]"
                >
                  {bucket.label}
                </text>
              )}
            </g>
          )
        })}
      </svg>
      <p className="mt-2 text-center text-[11px] text-muted-foreground">
        Scoring margin (points). Green = nailbiters, blue = wins, red = losses.
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// #50 Cumulative Points Race — running total line chart
// ---------------------------------------------------------------------------

export function PointsRaceChart({ rows }: { rows: Row[] }) {
  const width = 520
  const height = 240
  const padding = { top: 16, right: 16, bottom: 28, left: 44 }
  const weeks = getSeries(rows[0]).map((p) => p.week)
  if (weeks.length === 0) return <EmptyChart />
  const minWeek = Math.min(...weeks)
  const maxWeek = Math.max(...weeks)

  let maxTotal = 0
  for (const row of rows) {
    for (const p of getSeries(row)) {
      maxTotal = Math.max(maxTotal, p.cumulative_points)
    }
  }
  maxTotal = maxTotal || 1

  const x = (week: number) =>
    padding.left +
    ((week - minWeek) / Math.max(maxWeek - minWeek, 1)) *
      (width - padding.left - padding.right)
  const y = (pts: number) =>
    padding.top + (1 - pts / maxTotal) * (height - padding.top - padding.bottom)

  return (
    <div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        role="img"
        aria-label="Cumulative points race line chart"
      >
        {rows.map((row, i) => {
          const series = getSeries(row)
          const d = series
            .map(
              (p, j) =>
                `${j === 0 ? "M" : "L"} ${x(p.week).toFixed(1)} ${y(p.cumulative_points).toFixed(1)}`,
            )
            .join(" ")
          return (
            <path
              key={(row.roster_id as number) ?? i}
              d={d}
              fill="none"
              stroke={colorFor(i)}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          )
        })}
        {weeks.map((w) => (
          <text
            key={w}
            x={x(w)}
            y={height - 8}
            textAnchor="middle"
            className="fill-muted-foreground text-[9px]"
          >
            W{w}
          </text>
        ))}
      </svg>
      <Legend rows={rows} />
    </div>
  )
}

function EmptyChart() {
  return (
    <p className="py-6 text-center text-sm text-muted-foreground">
      Not enough data to chart yet
    </p>
  )
}

// ---------------------------------------------------------------------------
// Dispatcher
// ---------------------------------------------------------------------------

export function StatChart({ chart, rows }: { chart: string; rows: Row[] }) {
  switch (chart) {
    case "rank-trend":
      return <RankTrendChart rows={rows} />
    case "scatter":
      return <ScatterChart rows={rows} />
    case "margin":
      return <MarginHistogram rows={rows} />
    case "points-race":
      return <PointsRaceChart rows={rows} />
    default:
      return null
  }
}
