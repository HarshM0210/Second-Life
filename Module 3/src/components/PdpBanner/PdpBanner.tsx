import React from "react";
import {
  SizeGuidanceIcon,
  SocialProofIcon,
  ComparisonNudgeIcon,
  ClarifyingQaIcon,
} from "./icons";
import styles from "./PdpBanner.module.css";

type InterventionType =
  | "SIZE_GUIDANCE"
  | "SOCIAL_PROOF"
  | "COMPARISON_NUDGE"
  | "CLARIFYING_QA";

interface PdpBannerProps {
  interventionType: InterventionType;
  interventionCopy: string;
  onDismiss: () => void;
}

const ICON_MAP: Record<InterventionType, React.FC<{ className?: string }>> = {
  SIZE_GUIDANCE: SizeGuidanceIcon,
  SOCIAL_PROOF: SocialProofIcon,
  COMPARISON_NUDGE: ComparisonNudgeIcon,
  CLARIFYING_QA: ClarifyingQaIcon,
};

export const PdpBanner: React.FC<PdpBannerProps> = ({
  interventionType,
  interventionCopy,
  onDismiss,
}) => {
  const Icon = ICON_MAP[interventionType];

  return (
    <div className={styles.banner} role="alert">
      <Icon className={styles.icon} />
      <p className={styles.content}>{interventionCopy}</p>
      <button
        className={styles.dismissButton}
        onClick={onDismiss}
        aria-label="Dismiss return-risk guidance"
        type="button"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <line x1="4" y1="4" x2="12" y2="12" />
          <line x1="12" y1="4" x2="4" y2="12" />
        </svg>
      </button>
    </div>
  );
};
