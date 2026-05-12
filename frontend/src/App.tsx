import React, { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

type User = {
  id: string;
  email: string;
  name: string;
  role: string;
};

type DocumentSummary = {
  id: string;
  name: string;
  original_name: string;
  doc_type: string | null;
  file_size: number | null;
  page_count: number | null;
  mime_type: string | null;
  status: string;
  risk_level: string | null;
  schema_id: string | null;
  uploaded_by: string;
  uploaded_by_name?: string | null;
  confidence?: number | null;
  current_version?: number | null;
  created_at: string;
  updated_at: string;
};

type Extraction = {
  id: string;
  document_id: string;
  version: number;
  schema_id: string | null;
  fields: Record<string, any>;
  confidence_overall: number;
  confidence_per_field: Record<string, number>;
  llm_model: string | null;
  processing_time_ms: number | null;
  status: string;
  error: string | null;
  created_at: string;
};

type Review = {
  id: string;
  document_id: string;
  extraction_id: string;
  status: string;
  decision: string | null;
  notes: string | null;
  reviewed_at: string | null;
  reviewed_by: string | null;
  reviewed_by_name: string | null;
  created_at: string;
};

type DocumentDetail = DocumentSummary & {
  extractions: Extraction[];
  reviews: Review[];
};

type LoginResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

function formatBytes(bytes?: number | null) {
  if (!bytes && bytes !== 0) return "-";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

function prettyDate(value?: string | null) {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function statusClass(status: string) {
  switch (status) {
    case "extracted":
    case "approved":
      return "bg-emerald-100 text-emerald-700 border-emerald-200";
    case "needs_review":
    case "processing":
      return "bg-amber-100 text-amber-700 border-amber-200";
    case "error":
    case "rejected":
      return "bg-rose-100 text-rose-700 border-rose-200";
    default:
      return "bg-slate-100 text-slate-700 border-slate-200";
  }
}

function SectionCard({
  title,
  children,
  right,
}: {
  title: string;
  children: React.ReactNode;
  right?: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        {right}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

export default function DocIntelDashboard() {
  const [email, setEmail] = useState("admin@docintel.ai");
  const [password, setPassword] = useState("Admin123!");
  const [token, setToken] = useState<string>(() => localStorage.getItem("docintel_token") || "");
  const [me, setMe] = useState<User | null>(null);
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [docsError, setDocsError] = useState<string | null>(null);
  const [selectedDoc, setSelectedDoc] = useState<DocumentDetail | null>(null);
  const [selectedLoading, setSelectedLoading] = useState(false);

  const [uploadFiles, setUploadFiles] = useState<FileList | null>(null);
  const [schemaId, setSchemaId] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const authHeaders = useMemo(
    () => ({
      Authorization: token ? `Bearer ${token}` : "",
    }),
    [token],
  );

  async function login() {
    setLoginError(null);
    setLoginLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json", accept: "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Login failed (${res.status})`);
      }
      const data: LoginResponse = await res.json();
      setToken(data.access_token);
      setMe(data.user);
      localStorage.setItem("docintel_token", data.access_token);
    } catch (err: any) {
      setLoginError(err?.message || "Login failed");
    } finally {
      setLoginLoading(false);
    }
  }

  async function loadDocs() {
    if (!token) return;
    setDocsError(null);
    setDocsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/documents/?limit=20&offset=0`, {
        headers: {
          accept: "application/json",
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Failed to load documents (${res.status})`);
      }
      const data = await res.json();
      setDocs(data.documents || []);
    } catch (err: any) {
      setDocsError(err?.message || "Failed to load documents");
    } finally {
      setDocsLoading(false);
    }
  }

  async function loadDocument(docId: string) {
    if (!token) return;
    setSelectedLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/documents/${docId}`, {
        headers: {
          accept: "application/json",
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Failed to load document (${res.status})`);
      }
      const data = await res.json();
      setSelectedDoc(data);
    } catch (err) {
      console.error(err);
    } finally {
      setSelectedLoading(false);
    }
  }

  async function upload() {
    if (!uploadFiles || uploadFiles.length === 0) {
      setUploadError("Choose at least one file.");
      return;
    }
    setUploadError(null);
    setUploading(true);
    try {
      const form = new FormData();
      Array.from(uploadFiles).forEach((file) => form.append("files", file));
      if (schemaId.trim()) form.append("schema_id", schemaId.trim());

      const res = await fetch(`${API_BASE}/api/documents/`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: form,
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Upload failed (${res.status})`);
      }
      await loadDocs();
      setUploadFiles(null);
      setSchemaId("");
    } catch (err: any) {
      setUploadError(err?.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  useEffect(() => {
    if (token) {
      loadDocs();
      const timer = setInterval(loadDocs, 15000);
      return () => clearInterval(timer);
    }
  }, [token]);

  useEffect(() => {
    if (selectedDoc?.id) {
      loadDocument(selectedDoc.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docs]);

  const totals = useMemo(() => {
    const total = docs.length;
    const extracted = docs.filter((d) => d.status === "extracted").length;
    const review = docs.filter((d) => d.status === "needs_review").length;
    const avgConfidence =
      total > 0 ? Math.round(docs.reduce((sum, d) => sum + (d.confidence || 0), 0) / total) : 0;
    return { total, extracted, review, avgConfidence };
  }, [docs]);

  if (!token) {
    return (
      <div className="min-h-screen bg-slate-50 px-4 py-10">
        <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-3xl bg-white p-8 shadow-sm ring-1 ring-slate-200">
            <p className="text-sm font-medium text-indigo-600">DocIntel</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-slate-950">
              AI document intelligence dashboard
            </h1>
            <p className="mt-4 max-w-xl text-base leading-7 text-slate-600">
              Upload invoices, contracts, and reports. Review extracted fields, confidence scores,
              and human review status in one place.
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-3">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-sm text-slate-500">Extract</div>
                <div className="mt-1 text-lg font-semibold text-slate-900">OCR + LLM</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-sm text-slate-500">Validate</div>
                <div className="mt-1 text-lg font-semibold text-slate-900">Rules + review</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-sm text-slate-500">Track</div>
                <div className="mt-1 text-lg font-semibold text-slate-900">Audit logs</div>
              </div>
            </div>
          </div>

          <div className="rounded-3xl bg-white p-8 shadow-sm ring-1 ring-slate-200">
            <h2 className="text-2xl font-semibold text-slate-950">Sign in</h2>
            <p className="mt-2 text-sm text-slate-500">Use your seeded admin account.</p>

            <div className="mt-6 space-y-4">
              <label className="block">
                <span className="text-sm font-medium text-slate-700">Email</span>
                <input
                  className="mt-1 w-full rounded-xl border border-slate-300 px-4 py-3 outline-none ring-0 focus:border-indigo-500"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-slate-700">Password</span>
                <input
                  type="password"
                  className="mt-1 w-full rounded-xl border border-slate-300 px-4 py-3 outline-none ring-0 focus:border-indigo-500"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
              {loginError && <div className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{loginError}</div>}
              <button
                onClick={login}
                disabled={loginLoading}
                className="w-full rounded-xl bg-slate-950 px-4 py-3 font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loginLoading ? "Signing in..." : "Sign in"}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
          <div>
            <h1 className="text-xl font-semibold">DocIntel Dashboard</h1>
            <p className="text-sm text-slate-500">
              Signed in as {me?.name || "User"} · {me?.role || "role"}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={loadDocs}
              className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-50"
            >
              Refresh
            </button>
            <button
              onClick={() => {
                localStorage.removeItem("docintel_token");
                setToken("");
                setMe(null);
              }}
              className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
            >
              Log out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[360px_1fr_420px] lg:px-8">
        <aside className="space-y-6">
          <SectionCard title="Upload document">
            <div className="space-y-4">
              <label className="block">
                <span className="text-sm font-medium text-slate-700">Files</span>
                <input
                  type="file"
                  multiple
                  className="mt-1 block w-full rounded-xl border border-slate-300 bg-white p-2 text-sm"
                  onChange={(e) => setUploadFiles(e.target.files)}
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-slate-700">Schema ID (optional)</span>
                <input
                  placeholder="Leave blank for auto-classify"
                  className="mt-1 w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-indigo-500"
                  value={schemaId}
                  onChange={(e) => setSchemaId(e.target.value)}
                />
              </label>
              {uploadError && <div className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{uploadError}</div>}
              <button
                onClick={upload}
                disabled={uploading}
                className="w-full rounded-xl bg-indigo-600 px-4 py-3 font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {uploading ? "Uploading..." : "Upload"}
              </button>
            </div>
          </SectionCard>

          <SectionCard title="Quick stats">
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Documents" value={totals.total} />
              <Stat label="Extracted" value={totals.extracted} />
              <Stat label="Needs review" value={totals.review} />
              <Stat label="Avg confidence" value={`${totals.avgConfidence}%`} />
            </div>
          </SectionCard>

          <SectionCard title="API info">
            <div className="space-y-2 text-sm text-slate-600">
              <div><span className="font-medium text-slate-800">API:</span> {API_BASE}</div>
              <div><span className="font-medium text-slate-800">Token:</span> {token ? "Stored" : "Missing"}</div>
              <div><span className="font-medium text-slate-800">Auto refresh:</span> 15s</div>
            </div>
          </SectionCard>
        </aside>

        <section className="space-y-6">
          <SectionCard title="Documents" right={docsLoading ? <span className="text-xs text-slate-500">Loading…</span> : null}>
            {docsError && <div className="mb-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{docsError}</div>}
            <div className="overflow-hidden rounded-2xl border border-slate-200">
              <table className="min-w-full divide-y divide-slate-200 bg-white text-left text-sm">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-4 py-3 font-medium">Name</th>
                    <th className="px-4 py-3 font-medium">Type</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Confidence</th>
                    <th className="px-4 py-3 font-medium">Uploaded</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {docs.map((doc) => (
                    <tr
                      key={doc.id}
                      onClick={() => loadDocument(doc.id)}
                      className="cursor-pointer hover:bg-slate-50"
                    >
                      <td className="px-4 py-3 font-medium text-slate-900">{doc.name}</td>
                      <td className="px-4 py-3 text-slate-600">{doc.doc_type || "-"}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${statusClass(doc.status)}`}>
                          {doc.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-600">{doc.confidence ?? 0}%</td>
                      <td className="px-4 py-3 text-slate-600">{prettyDate(doc.created_at)}</td>
                    </tr>
                  ))}
                  {!docsLoading && docs.length === 0 && (
                    <tr>
                      <td className="px-4 py-10 text-center text-slate-500" colSpan={5}>
                        No documents yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </section>

        <aside className="space-y-6">
          <SectionCard title={selectedDoc ? selectedDoc.name : "Document details"} right={selectedLoading ? <span className="text-xs text-slate-500">Loading…</span> : null}>
            {!selectedDoc ? (
              <div className="text-sm text-slate-500">Select a document from the table to inspect its extraction details.</div>
            ) : (
              <div className="space-y-5">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <Meta label="Type" value={selectedDoc.doc_type || "-"} />
                  <Meta label="Status" value={selectedDoc.status} />
                  <Meta label="Confidence" value={`${selectedDoc.confidence ?? 0}%`} />
                  <Meta label="Risk" value={selectedDoc.risk_level || "-"} />
                  <Meta label="Pages" value={`${selectedDoc.page_count ?? 0}`} />
                  <Meta label="Size" value={formatBytes(selectedDoc.file_size)} />
                </div>

                <div>
                  <div className="mb-2 text-sm font-semibold text-slate-900">Latest extraction</div>
                  {selectedDoc.extractions?.[0] ? (
                    <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <div className="flex items-center justify-between text-xs text-slate-500">
                        <span>Model: {selectedDoc.extractions[0].llm_model || "-"}</span>
                        <span>{selectedDoc.extractions[0].confidence_overall}%</span>
                      </div>
                      <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-xl bg-white p-3 text-xs leading-6 text-slate-700 ring-1 ring-slate-200">
{JSON.stringify(selectedDoc.extractions[0].fields, null, 2)}
                      </pre>
                    </div>
                  ) : (
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
                      No extraction available.
                    </div>
                  )}
                </div>

                <div>
                  <div className="mb-2 text-sm font-semibold text-slate-900">Reviews</div>
                  <div className="space-y-2">
                    {selectedDoc.reviews?.length ? (
                      selectedDoc.reviews.map((r) => (
                        <div key={r.id} className="rounded-xl border border-slate-200 p-3 text-sm">
                          <div className="flex items-center justify-between">
                            <span className="font-medium">{r.status}</span>
                            <span className="text-slate-500">{prettyDate(r.created_at)}</span>
                          </div>
                          <div className="mt-1 text-slate-600">Decision: {r.decision || "-"}</div>
                        </div>
                      ))
                    ) : (
                      <div className="text-sm text-slate-500">No reviews yet.</div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </SectionCard>

          <SectionCard title="File actions">
            <div className="space-y-3 text-sm">
              <button
                onClick={() => selectedDoc && window.open(`${API_BASE}/api/documents/${selectedDoc.id}/download`, "_blank")}
                disabled={!selectedDoc}
                className="w-full rounded-xl border border-slate-300 px-4 py-3 font-medium hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Download original
              </button>
              <button
                onClick={() => selectedDoc && loadDocument(selectedDoc.id)}
                disabled={!selectedDoc}
                className="w-full rounded-xl bg-slate-950 px-4 py-3 font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Refresh details
              </button>
            </div>
          </SectionCard>
        </aside>
      </main>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-950">{value}</div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 font-medium text-slate-900">{value}</div>
    </div>
  );
}
