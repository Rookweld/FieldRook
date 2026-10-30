/**
 * Typed WebView2 shell bridge client (M026 contract section 2).
 *
 * The native shell hosts this same React UI over loopback and answers a
 * minimal allowlisted JSON protocol: `{op, id, params}` ->
 * `{id, ok, result | error}`. Allowed ops here are ONLY openFile,
 * saveFile, and getVersion. Unknown ops fail closed (never sent).
 *
 * Every call rejects with ShellBridgeError when the bridge is absent
 * (plain browser), so callers can fall back to honest browser behaviour
 * (file input / anchor download). No filesystem access happens here:
 * paths returned by the shell are labels only; bytes cross only inside
 * the validated message payload.
 */

export type ShellOp = "openFile" | "saveFile" | "getVersion";

export type ShellBridgeErrorCode = "unavailable" | "timeout" | "rejected" | "protocol";

export class ShellBridgeError extends Error {
  code: ShellBridgeErrorCode;

  constructor(code: ShellBridgeErrorCode, message: string) {
    super(message);
    this.code = code;
  }
}

export interface ShellOpenFileArgs {
  accept?: string;
  title?: string;
}

export interface ShellOpenFileResult {
  path: string;
  name: string;
  sizeBytes: number;
  /** Package bytes when the shell returns them; null means path-only. */
  contentBase64: string | null;
}

export interface ShellSaveFileArgs {
  filename: string;
  text: string;
  mime?: string;
}

export interface ShellSaveFileResult {
  path: string;
  bytesWritten: number;
}

export interface ShellVersionResult {
  version: string;
}

export type ShellPushEvent =
  | { event: "collector-dropped"; payload: { path: string; name: string } }
  | { event: string; payload: unknown };

interface ShellRequestMessage {
  op: ShellOp;
  id: string;
  params: Record<string, unknown>;
}

interface ShellResponseMessage {
  id: string;
  ok: boolean;
  result?: unknown;
  error?: unknown;
}

interface ChromeWebview {
  postMessage(message: unknown): void;
  addEventListener(type: "message", listener: (e: { data: unknown }) => void): void;
  removeEventListener(type: "message", listener: (e: { data: unknown }) => void): void;
}

declare global {
  interface Window {
    chrome?: { webview?: ChromeWebview };
  }
}

const DIALOG_TIMEOUT_MS = 120000;
const VERSION_TIMEOUT_MS = 10000;

let nextId = 0;
let listenerInstalled = false;

interface PendingCall {
  resolve: (value: unknown) => void;
  reject: (reason: ShellBridgeError) => void;
  timer: ReturnType<typeof setTimeout>;
}

const pending = new Map<string, PendingCall>();
const eventListeners = new Set<(event: ShellPushEvent) => void>();

function webview(): ChromeWebview | null {
  if (typeof window === "undefined") return null;
  return window.chrome?.webview ?? null;
}

export function isShellBridgeAvailable(): boolean {
  return webview() !== null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asResponseMessage(value: unknown): ShellResponseMessage | null {
  if (!isRecord(value)) return null;
  if (typeof value.id !== "string" || typeof value.ok !== "boolean") return null;
  return { id: value.id, ok: value.ok, result: value.result, error: value.error };
}

function dispatchMessage(data: unknown): void {
  const message = asResponseMessage(data);
  if (message) {
    const call = pending.get(message.id);
    if (!call) return;
    pending.delete(message.id);
    clearTimeout(call.timer);
    if (message.ok) {
      call.resolve(message.result);
    } else {
      const detail =
        typeof message.error === "string"
          ? message.error
          : isRecord(message.error) && typeof message.error.message === "string"
            ? message.error.message
            : "Shell rejected the request.";
      call.reject(new ShellBridgeError("rejected", detail));
    }
    return;
  }
  // The native shell posts validated window drops as
  // {kind:"fieldrook:file", fileName, path}; normalize to the typed
  // collector-dropped event. Malformed notices are ignored, never thrown.
  if (isRecord(data) && data.kind === "fieldrook:file") {
    const path = typeof data.path === "string" ? data.path : null;
    const name = typeof data.fileName === "string" ? data.fileName : null;
    if (path && name) {
      const pushed: ShellPushEvent = { event: "collector-dropped", payload: { path, name } };
      for (const listener of eventListeners) {
        try {
          listener(pushed);
        } catch {
          /* one bad subscriber must not break the bridge */
        }
      }
    }
    return;
  }
  // Id-less traffic is a server-push event.
  if (isRecord(data) && typeof data.event === "string") {
    const pushed: ShellPushEvent = { event: data.event, payload: data.payload };
    for (const listener of eventListeners) {
      try {
        listener(pushed);
      } catch {
        /* one bad subscriber must not break the bridge */
      }
    }
  }
}

function ensureListener(native: ChromeWebview): void {
  if (listenerInstalled) return;
  native.addEventListener("message", (e) => dispatchMessage(e.data));
  listenerInstalled = true;
}

function nextMessageId(op: ShellOp): string {
  nextId += 1;
  const rand = Math.floor(Math.random() * 0x1000000).toString(36);
  return `${op}-${Date.now().toString(36)}-${nextId}-${rand}`;
}

function callShell(op: ShellOp, params: Record<string, unknown>, timeoutMs: number): Promise<unknown> {
  const native = webview();
  if (!native) {
    return Promise.reject(new ShellBridgeError("unavailable", "No desktop shell bridge is present."));
  }
  ensureListener(native);
  const id = nextMessageId(op);
  const message: ShellRequestMessage = { op, id, params };
  return new Promise<unknown>((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new ShellBridgeError("timeout", `Shell operation ${op} timed out.`));
    }, timeoutMs);
    pending.set(id, { resolve, reject, timer });
    try {
      native.postMessage(message);
    } catch (e) {
      pending.delete(id);
      clearTimeout(timer);
      reject(
        new ShellBridgeError(
          "protocol",
          e instanceof Error ? `Shell postMessage failed: ${e.message}` : "Shell postMessage failed.",
        ),
      );
    }
  });
}

/** UTF-8 text → base64 without deprecated escape tricks; chunked for size. */
function utf8ToBase64(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  return btoa(binary);
}

function getString(record: Record<string, unknown>, key: string): string | null {
  const value = record[key];
  return typeof value === "string" ? value : null;
}

/** Shell + backend version for the desktop identity strip. */
export async function shellGetVersion(): Promise<ShellVersionResult> {
  const raw = await callShell("getVersion", {}, VERSION_TIMEOUT_MS);
  if (!isRecord(raw)) {
    throw new ShellBridgeError("protocol", "Shell getVersion returned a malformed result.");
  }
  const version = getString(raw, "version");
  if (!version) {
    throw new ShellBridgeError("protocol", "Shell getVersion returned no version string.");
  }
  return { version };
}

/**
 * Native open dialog for .zip collector packages. The browser cannot read
 * an arbitrary path, so import from bytes: when contentBase64 is null the
 * caller must say so honestly instead of pretending the import worked.
 */
export async function shellOpenFile(args: ShellOpenFileArgs = {}): Promise<ShellOpenFileResult> {
  const params: Record<string, unknown> = {};
  if (args.accept !== undefined) params.accept = args.accept;
  if (args.title !== undefined) params.title = args.title;
  const raw = await callShell("openFile", params, DIALOG_TIMEOUT_MS);
  if (!isRecord(raw)) {
    throw new ShellBridgeError("protocol", "Shell openFile returned a malformed result.");
  }
  const path = getString(raw, "path");
  const name = getString(raw, "name");
  const sizeBytes = raw.sizeBytes;
  if (!path || !name || typeof sizeBytes !== "number") {
    throw new ShellBridgeError("protocol", "Shell openFile returned an incomplete result.");
  }
  const content = raw.contentBase64;
  if (content !== undefined && content !== null && typeof content !== "string") {
    throw new ShellBridgeError("protocol", "Shell openFile returned malformed file bytes.");
  }
  return { path, name, sizeBytes, contentBase64: typeof content === "string" ? content : null };
}

/** Native save dialog for report/knowledge exports. */
export async function shellSaveFile(args: ShellSaveFileArgs): Promise<ShellSaveFileResult> {
  const raw = await callShell(
    "saveFile",
    { fileName: args.filename, contentBase64: utf8ToBase64(args.text) },
    DIALOG_TIMEOUT_MS,
  );
  if (!isRecord(raw)) {
    throw new ShellBridgeError("protocol", "Shell saveFile returned a malformed result.");
  }
  const path = getString(raw, "path");
  const bytesWritten = raw.bytesWritten;
  if (!path || typeof bytesWritten !== "number") {
    throw new ShellBridgeError("protocol", "Shell saveFile returned an incomplete result.");
  }
  return { path, bytesWritten };
}

/**
 * Subscribe to shell push events (id-less messages). The only known event
 * is "collector-dropped" (a .zip dropped onto the window); anything else
 * arrives as {event, payload} for forward compatibility.
 */
export function onShellEvent(listener: (event: ShellPushEvent) => void): () => void {
  eventListeners.add(listener);
  return () => {
    eventListeners.delete(listener);
  };
}
