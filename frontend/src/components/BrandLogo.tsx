import React from "react";

export type BrandLogoVariant = "full" | "compact" | "symbol" | "asset";

interface BrandLogoProps {
  variant?: BrandLogoVariant;
  className?: string;
  size?: "sm" | "md" | "lg" | "xl";
  animated?: boolean;
}

export const BrandSymbol: React.FC<{ size?: number; className?: string; animated?: boolean }> = ({
  size = 28,
  className = "",
  animated = false,
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`inline-block shrink-0 align-middle ${className}`}
      aria-label="Símbolo GridScope"
      role="img"
    >
      {/* Outer Glow Halo */}
      <circle cx="50" cy="50" r="44" stroke="var(--color-grid-yellow)" strokeWidth="1" strokeOpacity="0.25" strokeDasharray="3 3" />
      
      {/* Top Arc with Arrow */}
      <g className={animated ? "origin-center animate-[spin_8s_linear_infinite]" : ""}>
        <path
          d="M 22,35 A 36 36 0 0 1 78,35"
          stroke="var(--color-grid-white)"
          strokeWidth="6"
          strokeLinecap="round"
        />
        <path
          d="M 72,25 L 82,35 L 72,45"
          stroke="var(--color-grid-white)"
          strokeWidth="6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        
        {/* Bottom Arc with Arrow */}
        <path
          d="M 78,65 A 36 36 0 0 1 22,65"
          stroke="var(--color-grid-white)"
          strokeWidth="6"
          strokeLinecap="round"
        />
        <path
          d="M 28,75 L 18,65 L 28,55"
          stroke="var(--color-grid-white)"
          strokeWidth="6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </g>

      {/* GridScope Central Lightning Bolt */}
      <path
        d="M 54,16 L 33,52 L 50,52 L 44,84 L 68,48 L 50,48 Z"
        fill="var(--color-grid-yellow)"
        className="drop-shadow-[0_0_8px_rgba(255,212,0,0.6)]"
      />
    </svg>
  );
};

export const BrandLogo: React.FC<BrandLogoProps> = ({
  variant = "full",
  className = "",
  size = "md",
  animated = false,
}) => {
  if (variant === "asset") {
    const heightClass = {
      sm: "h-6",
      md: "h-9",
      lg: "h-12",
      xl: "h-16",
    }[size];

    return (
      <div className={`inline-flex items-center ${className}`}>
        <img
          src="/brand/logoGridScope.png"
          alt="GridScope — Dados. Equilíbrio. Futuro."
          className={`${heightClass} w-auto object-contain select-none`}
          loading="eager"
        />
      </div>
    );
  }

  if (variant === "symbol") {
    const symbolSizes = {
      sm: 24,
      md: 32,
      lg: 44,
      xl: 56,
    }[size];

    return <BrandSymbol size={symbolSizes} className={className} animated={animated} />;
  }

  const textSizes = {
    sm: {
      text: "text-lg",
      symbol: 18,
      sub: "text-[0.55rem] tracking-[0.24em] mt-0.5",
    },
    md: {
      text: "text-2xl",
      symbol: 24,
      sub: "text-[0.68rem] tracking-[0.28em] mt-1",
    },
    lg: {
      text: "text-3xl",
      symbol: 30,
      sub: "text-[0.78rem] tracking-[0.32em] mt-1.5",
    },
    xl: {
      text: "text-4xl",
      symbol: 38,
      sub: "text-[0.88rem] tracking-[0.36em] mt-2",
    },
  }[size];

  return (
    <div className={`inline-flex flex-col select-none ${className}`}>
      {/* Brand Logotype: Grid (grid-yellow) + Sc + Symbol(O) + pe (white) */}
      <div className="flex items-center leading-none">
        <span
          className={`font-display font-extrabold tracking-[-0.04em] text-grid-yellow ${textSizes.text}`}
        >
          Grid
        </span>
        <div className="inline-flex items-center">
          <span
            className={`font-display font-bold tracking-[-0.04em] text-white ${textSizes.text}`}
          >
            Sc
          </span>
          <span className="mx-[0.06em] inline-flex items-center justify-center">
            <BrandSymbol size={textSizes.symbol} animated={animated} />
          </span>
          <span
            className={`font-display font-bold tracking-[-0.04em] text-white ${textSizes.text}`}
          >
            pe
          </span>
        </div>
      </div>

      {/* Signature: Dados. Equilíbrio. Futuro. */}
      {variant === "full" && (
        <span
          className={`font-sans font-medium uppercase text-grid-gray transition-colors duration-200 ${textSizes.sub}`}
        >
          Dados. Equilíbrio. Futuro.
        </span>
      )}
    </div>
  );
};
