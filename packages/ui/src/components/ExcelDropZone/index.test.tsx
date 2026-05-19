/** ExcelDropZone unit tests — Story 3.E.1 AC5 #1-5. */

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExcelDropZone } from "./index";

function makeFile(name: string, sizeBytes: number, type = ""): File {
  // happy-dom honors the byte length used to construct the File for size.
  const blob = new Blob([new Uint8Array(sizeBytes)], { type });
  return new File([blob], name, { type });
}

function dropFile(file: File): void {
  const zone = screen.getByTestId("excel-drop-zone");
  fireEvent.drop(zone, { dataTransfer: { files: [file] } });
}

describe("ExcelDropZone", () => {
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

  it("triggers onFile when a valid .xlsx is dropped", () => {
    const onFile = vi.fn();
    const onReject = vi.fn();
    render(<ExcelDropZone onFile={onFile} onReject={onReject} />);

    dropFile(makeFile("vrptw.xlsx", 1024));

    expect(onFile).toHaveBeenCalledOnce();
    const passedFile = onFile.mock.calls[0]?.[0] as File;
    expect(passedFile.name).toBe("vrptw.xlsx");
    expect(onReject).not.toHaveBeenCalled();
  });

  it("triggers onReject with code=too_large when > maxSizeBytes", () => {
    const onFile = vi.fn();
    const onReject = vi.fn();
    render(<ExcelDropZone onFile={onFile} onReject={onReject} />);

    // 6 MB > default 5 MB limit
    dropFile(makeFile("big.xlsx", 6 * 1024 * 1024));

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

  it("triggers onReject with code=wrong_type when non-.xlsx is dropped", () => {
    const onFile = vi.fn();
    const onReject = vi.fn();
    render(<ExcelDropZone onFile={onFile} onReject={onReject} />);

    dropFile(makeFile("report.pdf", 1024));

    expect(onFile).not.toHaveBeenCalled();
    expect(onReject).toHaveBeenCalledOnce();
    const reason = onReject.mock.calls[0]?.[0] as { code: string };
    expect(reason.code).toBe("wrong_type");
  });

  it("falls back to console.warn when onReject is omitted and a reject happens", () => {
    const onFile = vi.fn();
    render(<ExcelDropZone onFile={onFile} />);

    dropFile(makeFile("big.xlsx", 6 * 1024 * 1024));

    expect(onFile).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalled();
    const firstCallArg = warnSpy.mock.calls[0]?.[0];
    expect(String(firstCallArg)).toContain("too_large");
  });

  it("never calls window.alert() across accept / reject paths", () => {
    const onFile = vi.fn();
    const onReject = vi.fn();
    render(<ExcelDropZone onFile={onFile} onReject={onReject} />);

    dropFile(makeFile("ok.xlsx", 1024));
    dropFile(makeFile("big.xlsx", 6 * 1024 * 1024));
    dropFile(makeFile("report.pdf", 1024));

    expect(alertSpy).not.toHaveBeenCalled();
  });
});
