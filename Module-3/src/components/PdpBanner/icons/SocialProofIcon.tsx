import React from "react";

interface SocialProofIconProps {
  className?: string;
}

/**
 * People/community icon representing social proof interventions.
 * Includes a <title> element for screen-reader accessibility.
 */
export const SocialProofIcon: React.FC<SocialProofIconProps> = ({
  className,
}) => {
  const titleId = "social-proof-icon-title";

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
      <title id={titleId}>Social Proof</title>
      {/* Center person */}
      <circle cx="12" cy="7" r="3" />
      <path d="M12 13c-3.31 0-6 1.79-6 4v1h12v-1c0-2.21-2.69-4-6-4z" />
      {/* Left person (smaller) */}
      <circle cx="5" cy="9" r="2" />
      <path d="M5 13c-1.66 0-3 0.9-3 2v1h3" />
      {/* Right person (smaller) */}
      <circle cx="19" cy="9" r="2" />
      <path d="M19 13c1.66 0 3 0.9 3 2v1h-3" />
    </svg>
  );
};
