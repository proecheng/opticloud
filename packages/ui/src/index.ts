/** OptiCloud UI Components — Tier 1 12 v1 stubs (Story 0.9-0.12).
 *
 * Architecture references:
 *   P72 packages/ui 单源 (UI Component Single-Source Discipline)
 *   P74 Cross-Service Storybook Visual Regression
 *
 * Component naming pattern (UX Spec Step 11):
 *   - PascalCase
 *   - 4 prefix categories: Action / Feedback / Display / Layout
 *
 * Tier 2 + Tier 3 components in business Epic stories (post Sprint 0 N3 unlock).
 */

// Hooks
export { useA11y } from "./hooks/useA11y";
export type { UseA11yOptions, UseA11yResult } from "./hooks/useA11y";

// Utility
export { cn } from "./lib/cn";

// Tier 1 12 v1 Components
export { APIKeyManager } from "./components/APIKeyManager";
export type { APIKey, APIKeyManagerProps } from "./components/APIKeyManager";

export { ConfidenceLabel } from "./components/ConfidenceLabel";
export type { ConfidenceLabelProps } from "./components/ConfidenceLabel";

export { ConfirmationModal } from "./components/ConfirmationModal";
export type { ConfirmationModalProps, ConfirmationVariant } from "./components/ConfirmationModal";

export { CreditsBalanceBucket } from "./components/CreditsBalanceBucket";
export type { CreditsBalanceBucketProps, CreditsBucket } from "./components/CreditsBalanceBucket";

export { ErrorBoundary, RFC7807Panel } from "./components/ErrorBoundary";
export type { RFC7807ErrorPayload } from "./components/ErrorBoundary";

export { ExcelDropZone } from "./components/ExcelDropZone";
export type { ExcelDropZoneProps } from "./components/ExcelDropZone";

export { SparklineKPI } from "./components/SparklineKPI";
export type { SparklineKPIProps } from "./components/SparklineKPI";

export { StatusCard } from "./components/StatusCard";
export type { StatusCardProps, StatusVariant } from "./components/StatusCard";

export { Toast } from "./components/Toast";
export type { ToastProps, ToastVariant } from "./components/Toast";

export { FilePicker } from "./components/FilePicker";
export type { FilePickerProps } from "./components/FilePicker";

export { LoadingShimmer } from "./components/LoadingShimmer";
export type { LoadingShimmerProps } from "./components/LoadingShimmer";

export { EmptyState } from "./components/EmptyState";
export type { EmptyStateProps } from "./components/EmptyState";

export const UI_VERSION = "0.0.1";
