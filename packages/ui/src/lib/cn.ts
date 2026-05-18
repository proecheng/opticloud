/** clsx + tailwind-merge utility (shadcn convention).
 *
 * Used throughout Tier 1 components for conditional className composition.
 */

import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
