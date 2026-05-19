/** API Keys management page — Story 1.3 (FR A2 完整).
 *
 * Auth-gated: redirects to /auth/login if no jwt_access in sessionStorage.
 * Lists own keys + create + revoke via auth-service CRUD endpoints.
 */
"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  type APIKeyCreateResponse,
  type APIKeyListItem,
  OptiCloudClientError,
  createApiKey,
  listAPIKeys,
  revokeAPIKey,
} from "@/lib/api";

const ALL_SCOPES = [
  "optimize:read",
  "optimize:write",
  "predict:read",
  "predict:write",
  "chat:read",
  "chat:write",
  "billing:read",
  "reproduce:read",
];

function keyStatus(k: APIKeyListItem): "active" | "expired" | "revoked" {
  if (k.revoked_at) return "revoked";
  if (k.expires_at && new Date(k.expires_at) < new Date()) return "expired";
  return "active";
}

export default function APIKeysPage(): JSX.Element {
  const router = useRouter();
  const [jwt, setJwt] = useState<string | null>(null);
  const [keys, setKeys] = useState<APIKeyListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [created, setCreated] = useState<APIKeyCreateResponse | null>(null);

  // Create form state
  const [label, setLabel] = useState("");
  const [scopes, setScopes] = useState<Set<string>>(new Set(["optimize:write"]));
  const [expiresInDays, setExpiresInDays] = useState<number | "never">(90);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? sessionStorage.getItem("jwt_access") : null;
    if (!stored) {
      router.push("/auth/login");
      return;
    }
    setJwt(stored);
  }, [router]);

  const refresh = useCallback(async () => {
    if (!jwt) return;
    setLoading(true);
    setError(null);
    try {
      const list = await listAPIKeys(jwt);
      setKeys(list);
    } catch (e) {
      setError(e instanceof OptiCloudClientError ? `${e.title}: ${e.detail}` : String(e));
    } finally {
      setLoading(false);
    }
  }, [jwt]);

  useEffect(() => {
    if (jwt) void refresh();
  }, [jwt, refresh]);

  const handleCreate = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    if (!jwt || scopes.size === 0) return;
    setLoading(true);
    setError(null);
    try {
      const result = await createApiKey(jwt, {
        label,
        scope: Array.from(scopes),
        expires_in_days: expiresInDays === "never" ? undefined : expiresInDays,
      });
      setCreated(result);
      setLabel("");
      setScopes(new Set(["optimize:write"]));
      void refresh();
    } catch (e) {
      setError(e instanceof OptiCloudClientError ? `${e.title}: ${e.detail}` : String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleRevoke = async (keyId: string): Promise<void> => {
    if (!jwt) return;
    if (!confirm("Revoke this key? This cannot be undone.")) return;
    setLoading(true);
    try {
      await revokeAPIKey(jwt, keyId);
      void refresh();
    } catch (e) {
      setError(e instanceof OptiCloudClientError ? `${e.title}: ${e.detail}` : String(e));
    } finally {
      setLoading(false);
    }
  };

  const toggleScope = (s: string): void => {
    setScopes((prev) => {
      const next = new Set(prev);
      if (next.has(s)) next.delete(s);
      else next.add(s);
      return next;
    });
  };

  return (
    <main className="container mx-auto max-w-4xl p-8">
      <header className="mb-6 flex items-baseline justify-between">
        <h1 className="text-2xl font-bold">API Keys</h1>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-muted-foreground">{keys.length} key(s)</span>
          <button
            type="button"
            onClick={() => {
              setShowCreate(true);
              setCreated(null);
            }}
            className="rounded-md bg-primary px-4 py-2 text-white hover:bg-primary/90"
          >
            Create new key
          </button>
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded-md border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
          {error}
        </div>
      )}

      {created && (
        <div
          className="mb-4 rounded-md border border-warning/40 bg-warning/10 p-4"
          data-testid="api-key-created-once"
        >
          <p className="text-sm font-semibold text-warning">
            ⚠ Copy this key now — it will NOT be shown again
          </p>
          <code className="mt-2 block break-all rounded bg-background p-3 font-mono text-sm">
            {created.api_key}
          </code>
          <button
            type="button"
            onClick={() => setCreated(null)}
            className="mt-2 text-xs text-primary hover:underline"
          >
            Done — hide
          </button>
        </div>
      )}

      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="mb-6 rounded-md border border-border bg-background p-4"
        >
          <h2 className="mb-3 font-semibold">Create API Key</h2>
          <fieldset className="mb-3" disabled={loading}>
            <label htmlFor="label" className="mb-1 block text-sm font-medium">
              Label *
            </label>
            <input
              id="label"
              type="text"
              required
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="prod / dev / postman"
              className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
          </fieldset>

          <fieldset className="mb-3" disabled={loading}>
            <legend className="mb-1 block text-sm font-medium">Scope (select ≥1)</legend>
            <div className="grid grid-cols-2 gap-2 text-sm">
              {ALL_SCOPES.map((s) => (
                <label key={s} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={scopes.has(s)}
                    onChange={() => toggleScope(s)}
                  />
                  <span className="font-mono">{s}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset className="mb-3" disabled={loading}>
            <label htmlFor="expires" className="mb-1 block text-sm font-medium">
              Expires
            </label>
            <select
              id="expires"
              value={String(expiresInDays)}
              onChange={(e) => {
                const v = e.target.value;
                setExpiresInDays(v === "never" ? "never" : Number(v));
              }}
              className="min-h-touch rounded-md border border-border bg-background px-3 py-2"
            >
              <option value="30">30 days</option>
              <option value="90">90 days</option>
              <option value="365">365 days</option>
              <option value="never">Never</option>
            </select>
          </fieldset>

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={loading || !label || scopes.size === 0}
              className="rounded-md bg-primary px-4 py-2 text-white hover:bg-primary/90 disabled:opacity-50"
            >
              Create
            </button>
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="rounded-md border border-border px-4 py-2 hover:bg-muted"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <table className="w-full text-sm" data-testid="api-keys-table">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase text-muted-foreground">
            <th className="py-2">Label</th>
            <th className="py-2">Prefix</th>
            <th className="py-2">Scope</th>
            <th className="py-2">Created</th>
            <th className="py-2">Last used</th>
            <th className="py-2">Expires</th>
            <th className="py-2">Status</th>
            <th className="py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {keys.length === 0 && !loading && (
            <tr>
              <td colSpan={8} className="py-8 text-center text-muted-foreground">
                No keys yet — create your first one.
              </td>
            </tr>
          )}
          {keys.map((k) => {
            const status = keyStatus(k);
            return (
              <tr key={k.id} className="border-b border-border/40">
                <td className="py-2">{k.label}</td>
                <td className="py-2 font-mono">{k.prefix}</td>
                <td className="py-2 text-xs">{k.scope.join(", ")}</td>
                <td className="py-2 text-xs">{new Date(k.created_at).toLocaleDateString()}</td>
                <td className="py-2 text-xs">
                  {k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : "—"}
                </td>
                <td className="py-2 text-xs">
                  {k.expires_at ? new Date(k.expires_at).toLocaleDateString() : "Never"}
                </td>
                <td className="py-2">
                  <span
                    className={
                      status === "active"
                        ? "rounded bg-success/10 px-2 py-0.5 text-xs text-success"
                        : status === "expired"
                          ? "rounded bg-warning/10 px-2 py-0.5 text-xs text-warning"
                          : "rounded bg-danger/10 px-2 py-0.5 text-xs text-danger"
                    }
                  >
                    {status}
                  </span>
                </td>
                <td className="py-2">
                  {status === "active" && (
                    <button
                      type="button"
                      onClick={() => void handleRevoke(k.id)}
                      className="text-xs text-danger hover:underline"
                    >
                      Revoke
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </main>
  );
}
