import React from "react";

interface SizeGuidanceIconProps {
  className?: string;
}

/**
 * Ruler/measuring icon representing size guidance interventions.
 * Includes a <title> element for screen-reader accessibility.
 */
export const SizeGuidanceIcon: React.FC<SizeGuidanceIconProps> = ({
  className,
}) => {
  const titleId = "size-guidance-icon-title";

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
      <title id={titleId}>Size Guidance</title>
      {/* Ruler body */}
      <rect x="3" y="10" width="18" height="4" rx="1" />
      {/* Ruler tick marks */}
      <line x1="6" y1="10" x2="6" y2="7" />
      <line x1="9" y1="10" x2="9" y2="8" />
      <line x1="12" y1="10" x2="12" y2="7" />
      <line x1="15" y1="10" x2="15" y2="8" />
      <line x1="18" y1="10" x2="18" y2="7" />
    </svg>
  );
};
