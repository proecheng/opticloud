/** FilePicker unit tests — Story 3.E.1 AC5 #6-9. */

import { fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FilePicker } from "./index";

function makeFile(name: string, sizeBytes: number): File {
  const blob = new Blob([new Uint8Array(sizeBytes)]);
  return new File([blob], name);
}

function pickFile(container: HTMLElement, file: File): void {
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  // happy-dom honors a FileList synthesized via Object.defineProperty.
  Object.defineProperty(input, "files", { value: [file], configurable: true });
  fireEvent.change(input);
}

describe("FilePicker", () => {
  let alertSpy: ReturnType<typeof vi.spyOn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    alertSpy = vi.spyOn(window, "alert").mockImplementation(() => undefined);
    warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
  });

  afterEach(() => {
    alertSpy.mockRestore();
    warnSpy.mockRestore();
  });

  it("triggers onFile when picking a valid file", () => {
    const onFile = vi.fn();
    const onReject = vi.fn();
    const { container } = render(
      <FilePicker ariaLabel="test.picker" onFile={onFile} onReject={onReject} />,
    );

    pickFile(container, makeFile("ok.xlsx", 1024));

    expect(onFile).toHaveBeenCalledOnce();
    expect(onReject).not.toHaveBeenCalled();
  });

  it("triggers onReject with code=too_large when > maxSizeBytes", () => {
    const onFile = vi.fn();
    const onReject = vi.fn();
    const { container } = render(
      <FilePicker ariaLabel="test.picker" onFile={onFile} onReject={onReject} />,
    );

    pickFile(container, makeFile("big.xlsx", 6 * 1024 * 1024));

    expect(onFile).not.toHaveBeenCalled();
    expect(onReject).toHaveBeenCalledOnce();
    const reason = onReject.mock.calls[0]?.[0] as {
      code: string;
      sizeMB: string;
      maxMB: string;
    };
    expect(reason.code).toBe("too_large");
    expect(reason.sizeMB).toBe("6.0");
    expect(reason.maxMB).toBe("5");
  });

  it("falls back to console.warn when onReject is omitted and oversize is picked", () => {
    const onFile = vi.fn();
    const { container } = render(
      <FilePicker ariaLabel="test.picker" onFile={onFile} />,
    );

    pickFile(container, makeFile("big.xlsx", 6 * 1024 * 1024));

    expect(onFile).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalled();
    expect(String(warnSpy.mock.calls[0]?.[0])).toContain("too_large");
  });

  it("never calls window.alert() across accept / reject paths", () => {
    const onFile = vi.fn();
    const onReject = vi.fn();
    const { container } = render(
      <FilePicker ariaLabel="test.picker" onFile={onFile} onReject={onReject} />,
    );

    pickFile(container, makeFile("ok.xlsx", 1024));
    pickFile(container, makeFile("big.xlsx", 6 * 1024 * 1024));

    expect(alertSpy).not.toHaveBeenCalled();
  });
});
