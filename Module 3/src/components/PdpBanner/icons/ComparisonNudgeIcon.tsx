import React from "react";

interface ComparisonNudgeIconProps {
  className?: string;
}

/**
 * Balance/scale icon representing comparison nudge interventions.
 * Includes a <title> element for screen-reader accessibility.
 */
export const ComparisonNudgeIcon: React.FC<ComparisonNudgeIconProps> = ({
  className,
}) => {
  const titleId = "comparison-nudge-icon-title";

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      role="img"
      aria-labelledby={titleId}
      className={className}
    >
      <title id={titleId}>Comparison Nudge</title>
      {/* Balance beam */}
      <line x1="12" y1="3" x2="12" y2="21" />
      <line x1="4" y1="7" x2="20" y2="7" />
      {/* Left pan */}
      <path d="M4 7l-1 6h6l-1-6" />
      {/* Right pan */}
      <path d="M20 7l-1 6h-6l1-6" />
      {/* Base */}
      <line x1="9" y1="21" x2="15" y2="21" />
    </svg>
  );
};
