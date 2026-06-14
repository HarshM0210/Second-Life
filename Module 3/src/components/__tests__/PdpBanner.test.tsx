import React from "react";
import { render, screen } from "@testing-library/react";
import { PdpBanner } from "../PdpBanner/PdpBanner";

// Mock CSS modules to avoid import errors in test environment
jest.mock("../PdpBanner/PdpBanner.module.css", () => ({
  banner: "banner",
  icon: "icon",
  content: "content",
  dismissButton: "dismissButton",
}));

describe("PdpBanner", () => {
  const defaultProps = {
    interventionCopy: "Test intervention copy",
    onDismiss: jest.fn(),
  };

  describe("renders correct icon for each interventionType", () => {
    it("renders Size Guidance icon for SIZE_GUIDANCE", () => {
      render(<PdpBanner {...defaultProps} interventionType="SIZE_GUIDANCE" />);

      expect(screen.getByTitle("Size Guidance")).toBeInTheDocument();
    });

    it("renders Social Proof icon for SOCIAL_PROOF", () => {
      render(<PdpBanner {...defaultProps} interventionType="SOCIAL_PROOF" />);

      expect(screen.getByTitle("Social Proof")).toBeInTheDocument();
    });

    it("renders Comparison Nudge icon for COMPARISON_NUDGE", () => {
      render(
        <PdpBanner {...defaultProps} interventionType="COMPARISON_NUDGE" />,
      );

      expect(screen.getByTitle("Comparison Nudge")).toBeInTheDocument();
    });

    it("renders Clarifying Q&A icon for CLARIFYING_QA", () => {
      render(<PdpBanner {...defaultProps} interventionType="CLARIFYING_QA" />);

      // The icon title uses &amp; in JSX which renders as &
      expect(screen.getByTitle("Clarifying Q&A")).toBeInTheDocument();
    });
  });

  describe("dismiss button accessibility", () => {
    it("has correct aria-label on dismiss button", () => {
      render(<PdpBanner {...defaultProps} interventionType="SIZE_GUIDANCE" />);

      const dismissButton = screen.getByRole("button", {
        name: "Dismiss return-risk guidance",
      });
      expect(dismissButton).toBeInTheDocument();
    });
  });

  it("renders the intervention copy text", () => {
    render(<PdpBanner {...defaultProps} interventionType="SOCIAL_PROOF" />);

    expect(screen.getByText("Test intervention copy")).toBeInTheDocument();
  });
});
