import React from "react";
import { CaretLeft, CaretRight } from "@phosphor-icons/react";

export const PAGE_SIZE = 20;

export function Pagination({
  page,
  pageCount,
  total,
  pageSize = PAGE_SIZE,
  onPrev,
  onNext,
  testId = "pagination",
}) {
  if (!total) return null;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  return (
    <div
      data-testid={testId}
      className="flex items-center justify-between gap-3 flex-wrap px-1 py-3 text-sm"
    >
      <span className="text-muted-foreground">
        Menampilkan <span className="mono">{start}</span>–
        <span className="mono">{end}</span> dari{" "}
        <span className="mono">{total}</span>
      </span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          data-testid={`${testId}-prev`}
          disabled={page <= 1}
          onClick={onPrev}
          className="inline-flex items-center gap-1 border border-border bg-secondary hover:bg-slate-100 rounded-sm px-3 py-1.5 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <CaretLeft size={14} weight="bold" /> Sebelumnya
        </button>
        <span className="mono text-muted-foreground">
          {page}/{pageCount}
        </span>
        <button
          type="button"
          data-testid={`${testId}-next`}
          disabled={page >= pageCount}
          onClick={onNext}
          className="inline-flex items-center gap-1 border border-border bg-secondary hover:bg-slate-100 rounded-sm px-3 py-1.5 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Berikutnya <CaretRight size={14} weight="bold" />
        </button>
      </div>
    </div>
  );
}
