import { useReactTable, type SortingState, flexRender } from '@tanstack/react-table'
import type { ColumnDef, CellContext } from '@tanstack/table-core'
import { getCoreRowModel, getSortedRowModel, getPaginationRowModel } from '@tanstack/table-core'
import type { Claim } from '../services/claims'

type ClaimsTableProps = {
  items: Claim[]
  pageIndex: number // 0-based
  pageSize: number
  total: number
  onPageChange: (newPageIndex: number) => void
  onRowClick: (c: Claim) => void
  sorting: SortingState
  onSortingChange: (s: SortingState) => void
}

export default function ClaimsTable({ items, pageIndex, pageSize, total, onPageChange, onRowClick, sorting, onSortingChange }: ClaimsTableProps) {
  const columns: ColumnDef<Claim, unknown>[] = [
    { accessorKey: 'claim_id', header: 'Claim ID' },
    { id: 'patient_name', accessorFn: (row: Claim) => row.patient_name ?? '', header: 'Patient' },
    { id: 'payer_name', accessorFn: (row: Claim) => row.payer_name ?? '', header: 'Payer' },
    {
      accessorKey: 'amount',
      header: 'Amount',
      cell: (info: CellContext<Claim, unknown>) => `$${Number(info.getValue() as number).toFixed(2)}`,
    },
    { accessorKey: 'status', header: 'Status' },
    { accessorKey: 'risk_level', header: 'Risk' },
    {
      accessorKey: 'risk_score',
      header: 'Score',
      cell: (info: CellContext<Claim, unknown>) => `${info.getValue() as number}%`,
    },
  ]

  const table = useReactTable({
    data: items,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    // keep table pagination and sorting state in sync with server-side pagination
    state: {
      pagination: {
        pageIndex,
        pageSize,
      },
      sorting,
    },
    onSortingChange: (updaterOrValue) => {
      if (typeof updaterOrValue === 'function') {
        const next = updaterOrValue(sorting)
        onSortingChange(next)
      } else {
        onSortingChange(updaterOrValue)
      }
    },
    pageCount: Math.max(1, Math.ceil(total / pageSize)),
  })

  const pageCount = Math.max(1, Math.ceil(total / pageSize))

  return (
    <>
      <table className="w-full table-auto">
        <thead>
          {table.getHeaderGroups().map(hg => (
            <tr key={hg.id}>
              {hg.headers.map(h => (
                <th
                  key={h.id}
                  className="text-left p-2 text-sm text-slate-500"
                  {...(h.column.getCanSort?.() ? { onClick: h.column.getToggleSortingHandler() } : {})}
                  style={{ cursor: h.column.getCanSort?.() ? 'pointer' : 'default' }}
                >
                  {h.isPlaceholder ? null : (
                    <div className="flex items-center gap-2">
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {h.column.getIsSorted ? (
                        <span className="text-xs text-slate-400">{h.column.getIsSorted() === 'asc' ? '▲' : h.column.getIsSorted() === 'desc' ? '▼' : ''}</span>
                      ) : null}
                    </div>
                  )}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map(row => (
            <tr key={row.id} className="cursor-pointer hover:bg-slate-50" onClick={() => onRowClick(row.original as Claim)}>
              {row.getVisibleCells().map(cell => (
                <td key={cell.id} className="p-2 text-sm text-slate-700">
                  {cell.column.id === 'status' ? (
                    String(cell.getValue()) === 'Denied' ? (
                      <span className="bg-red-200 text-red-800 inline-flex items-center rounded px-2 py-1 text-xs font-medium">{String(cell.getValue())}</span>
                    ) : String(cell.getValue()) === 'Paid' ? (
                      <span className="bg-green-200 text-green-800 inline-flex items-center rounded px-2 py-1 text-xs font-medium">{String(cell.getValue())}</span>
                    ) : (
                      <span className="bg-amber-200 text-amber-800 inline-flex items-center rounded px-2 py-1 text-xs font-medium">{String(cell.getValue())}</span>
                    )
                  ) : cell.column.id === 'risk_level' ? (
                    String(cell.getValue()) === 'High' ? (
                      <span className="bg-red-200 text-red-800 inline-flex items-center rounded px-2 py-1 text-xs font-medium">{String(cell.getValue())}</span>
                    ) : String(cell.getValue()) === 'Medium' ? (
                      <span className="bg-amber-200 text-amber-800 inline-flex items-center rounded px-2 py-1 text-xs font-medium">{String(cell.getValue())}</span>
                    ) : (
                      <span className="bg-green-200 text-green-800 inline-flex items-center rounded px-2 py-1 text-xs font-medium">{String(cell.getValue())}</span>
                    )
                  ) : (
                    flexRender(cell.column.columnDef.cell, cell.getContext())
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-3 flex items-center justify-between">
        <div>
          <button className="mr-2 rounded border px-3 py-1" onClick={() => onPageChange(Math.max(0, pageIndex - 1))} disabled={pageIndex <= 0}>
            Previous
          </button>
          <button className="rounded border px-3 py-1" onClick={() => onPageChange(Math.min(pageCount - 1, pageIndex + 1))} disabled={pageIndex >= pageCount - 1}>
            Next
          </button>
        </div>
        <div className="text-sm text-slate-500">Page {pageIndex + 1} of {pageCount}</div>
      </div>
    </>
  )
}
