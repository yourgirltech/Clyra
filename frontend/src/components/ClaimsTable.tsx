import { useReactTable, type SortingState, flexRender } from '@tanstack/react-table'
import type { ColumnDef, CellContext } from '@tanstack/table-core'
import { getCoreRowModel, getSortedRowModel, getPaginationRowModel } from '@tanstack/table-core'
import { ChevronLeft, ChevronRight, ChevronsUpDown } from 'lucide-react'
import type { Claim } from '../services/claims'
import { RiskBadge, StatusBadge } from './ui/Badge'

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
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] table-auto">
          <thead>
            {table.getHeaderGroups().map(hg => (
              <tr key={hg.id} className="border-b border-slate-100">
                {hg.headers.map(h => (
                  <th
                    key={h.id}
                    className="px-3 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-400 select-none"
                    {...(h.column.getCanSort?.() ? { onClick: h.column.getToggleSortingHandler() } : {})}
                    style={{ cursor: h.column.getCanSort?.() ? 'pointer' : 'default' }}
                  >
                    {h.isPlaceholder ? null : (
                      <div className="flex items-center gap-1.5">
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        {h.column.getCanSort?.() && (
                          <span className="text-slate-300">
                            {h.column.getIsSorted() === 'asc' ? (
                              <ChevronRight className="h-3.5 w-3.5 -rotate-90" />
                            ) : h.column.getIsSorted() === 'desc' ? (
                              <ChevronRight className="h-3.5 w-3.5 rotate-90" />
                            ) : (
                              <ChevronsUpDown className="h-3.5 w-3.5" />
                            )}
                          </span>
                        )}
                      </div>
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-slate-100">
            {table.getRowModel().rows.map(row => (
              <tr key={row.id} className="cursor-pointer transition hover:bg-slate-50" onClick={() => onRowClick(row.original as Claim)}>
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} className="px-3 py-3 text-sm text-slate-700">
                    {cell.column.id === 'status' ? (
                      <StatusBadge status={String(cell.getValue())} />
                    ) : cell.column.id === 'risk_level' ? (
                      <RiskBadge level={String(cell.getValue())} />
                    ) : (
                      flexRender(cell.column.columnDef.cell, cell.getContext())
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-4">
        <div className="flex items-center gap-2">
          <button
            className="flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-slate-200 disabled:hover:text-slate-600"
            onClick={() => onPageChange(Math.max(0, pageIndex - 1))}
            disabled={pageIndex <= 0}
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </button>
          <button
            className="flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-slate-200 disabled:hover:text-slate-600"
            onClick={() => onPageChange(Math.min(pageCount - 1, pageIndex + 1))}
            disabled={pageIndex >= pageCount - 1}
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
        <div className="text-sm text-slate-500">
          Page <span className="font-medium text-slate-700">{pageIndex + 1}</span> of {pageCount}
        </div>
      </div>
    </>
  )
}
