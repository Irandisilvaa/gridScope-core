import React from "react";
import { CaretLeft, CaretRight } from "@phosphor-icons/react";

interface PaginationProps {
  currentPage: number;
  totalItems: number;
  pageSize?: number;
  onPageChange: (page: number) => void;
  className?: string;
}

export const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  totalItems,
  pageSize = 7,
  onPageChange,
  className = "",
}) => {
  const totalPages = Math.ceil(totalItems / pageSize);

  if (totalPages <= 1) return null;

  const startItem = (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalItems);

  // Generate page numbers to show
  const getPageNumbers = () => {
    const pages: (number | string)[] = [];
    if (totalPages <= 5) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      if (currentPage > 3) pages.push("...");
      const start = Math.max(2, currentPage - 1);
      const end = Math.min(totalPages - 1, currentPage + 1);
      for (let i = start; i <= end; i++) {
        if (!pages.includes(i)) pages.push(i);
      }
      if (currentPage < totalPages - 2) pages.push("...");
      if (!pages.includes(totalPages)) pages.push(totalPages);
    }
    return pages;
  };

  return (
    <div
      className={`flex flex-wrap items-center justify-between gap-3 border-t border-[#1F1F1F] bg-[#0A0A0A] px-3 py-2.5 font-mono text-xs text-[#8A8A8A] ${className}`}
    >
      <div className="text-[0.7rem]">
        Mostrando <strong className="text-white">{startItem}</strong> a{" "}
        <strong className="text-white">{endItem}</strong> de{" "}
        <strong className="text-[#FFD400]">{totalItems}</strong> registros
      </div>

      <div className="flex items-center gap-1.5">
        {/* Previous Button */}
        <button
          type="button"
          disabled={currentPage === 1}
          onClick={() => onPageChange(currentPage - 1)}
          className="flex h-7 w-7 items-center justify-center rounded-lg border border-[#262626] bg-[#141414] text-[#8A8A8A] transition-colors hover:border-[#FFD400] hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
          title="Página anterior"
          aria-label="Página anterior"
        >
          <CaretLeft size={14} />
        </button>

        {/* Page Number Buttons */}
        {getPageNumbers().map((p, idx) =>
          typeof p === "number" ? (
            <button
              key={idx}
              type="button"
              onClick={() => onPageChange(p)}
              className={`flex h-7 min-w-[28px] px-1.5 items-center justify-center rounded-lg border text-xs font-semibold transition-colors ${
                currentPage === p
                  ? "border-[#FFD400] bg-[#FFD400] text-black shadow-[0_0_8px_rgba(255,212,0,0.3)]"
                  : "border-[#222222] bg-[#121212] text-[#8A8A8A] hover:border-[#383838] hover:text-white"
              }`}
            >
              {p}
            </button>
          ) : (
            <span key={idx} className="px-1 text-[#555555]">
              {p}
            </span>
          )
        )}

        {/* Next Button */}
        <button
          type="button"
          disabled={currentPage === totalPages}
          onClick={() => onPageChange(currentPage + 1)}
          className="flex h-7 w-7 items-center justify-center rounded-lg border border-[#262626] bg-[#141414] text-[#8A8A8A] transition-colors hover:border-[#FFD400] hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
          title="Próxima página"
          aria-label="Próxima página"
        >
          <CaretRight size={14} />
        </button>
      </div>
    </div>
  );
};
