import { useEffect, useState } from "react";

export default function AnimatedLock({ loading = true }) {
  const [unlocked, setUnlocked] = useState(true);

  useEffect(() => {
    if (!loading) {
      // Small delay makes the transition feel intentional
      const timer = setTimeout(() => {
        setUnlocked(true);
      }, 250);

      return () => clearTimeout(timer);
    }

    setUnlocked(false);
  }, [loading]);

  return (
    <div className="relative mx-auto mb-6 flex h-16 w-16 items-center justify-center">
      {/* Outer ambient glow */}
      <div
        className={`absolute inset-0 rounded-2xl bg-purple-500/30 blur-xl transition-all duration-1000 ${
          loading
            ? "scale-75 opacity-40 animate-pulse"
            : "scale-110 opacity-80"
        }`}
      />

      {/* Main logo container */}
      <div
        className={`
          relative z-10 flex h-16 w-16 items-center justify-center
          rounded-2xl bg-purple-500
          shadow-lg shadow-purple-300/50
          transition-all duration-700
          ${loading ? "rotate-3" : "rotate-0 scale-105"}
        `}
      >
        {/* Animated shine */}
        <div
          className={`
            pointer-events-none absolute inset-0 overflow-hidden rounded-2xl
            transition-opacity duration-500
            ${loading ? "opacity-100" : "opacity-0"}
          `}
        >
          <div className="absolute -left-20 top-0 h-full w-12 rotate-12 bg-white/20 blur-md animate-[shine_2.5s_ease-in-out_infinite]" />
        </div>

        {/* Lock */}
        <svg
          className={`
            relative z-10 h-8 w-8 text-white
            transition-all duration-700
            ${loading ? "animate-[lockGlow_2s_ease-in-out_infinite]" : ""}
          `}
          fill="none"
          viewBox="0 0 24 24"
        >
          {/* Lock body */}
          <rect
            x="4"
            y="10"
            width="16"
            height="10"
            rx="2"
            className={`
              stroke-current
              transition-all duration-500
              ${
                loading
                  ? "opacity-40"
                  : "opacity-100"
              }
            `}
            strokeWidth="2"
          />

          {/* Lock shackle */}
          <path
            d={
              unlocked
                ? "M8 10V7a4 4 0 018 0v1"
                : "M8 10V7a4 4 0 018 0v3"
            }
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            className={`
              transition-all duration-700
              ${
                loading
                  ? "opacity-30"
                  : "opacity-100"
              }
            `}
          />

          {/* Keyhole */}
          <circle
            cx="12"
            cy="14.5"
            r="1"
            fill="currentColor"
            className={`
              transition-all duration-500
              ${loading ? "opacity-30" : "opacity-100"}
            `}
          />

          <path
            d="M12 15.5v2"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            className={`
              transition-all duration-500
              ${loading ? "opacity-30" : "opacity-100"}
            `}
          />
        </svg>

        {/* Completion flash */}
        {!loading && (
          <div className="absolute inset-0 rounded-2xl border-2 border-white/40 animate-ping" />
        )}
      </div>
    </div>
  );
}
