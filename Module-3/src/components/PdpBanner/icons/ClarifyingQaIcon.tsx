import React from "react";

interface ClarifyingQaIconProps {
  className?: string;
}

/**
 * Question mark / chat bubble icon representing clarifying Q&A interventions.
 * Includes a <title> element for screen-reader accessibility.
 */
export const ClarifyingQaIcon: React.FC<ClarifyingQaIconProps> = ({
  className,
}) => {
  const titleId = "clarifying-qa-icon-title";

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
      <title id={titleId}>Clarifying Q&amp;A</title>
      {/* Chat bubble */}
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10z" />
      {/* Question mark */}
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <circle cx="12" cy="17" r="0.5" fill="currentColor" />
    </svg>
  );
};
