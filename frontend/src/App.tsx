import React, { useEffect, useMemo, useState, useCallback } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// ─── Types (matched exactly to backend schemas.py) ────────────────────────────
type User = { id: string; email: string; name: string; role: string; department?: string | null; avatar_initials?: string | null; last_login?: string | null; created_at: string };
type SchemaSummary = { id: string; name: string; doc_type: string; version: string; status: string; doc_count: number; created_at: string };
type DocumentSummary = {
  id: string; name: string; original_name: string; doc_type: string | null;
  file_size: number | null; page_count: number | null; mime_type: string | null;
  status: string; risk_level: string | null; schema_id: string | null;
  uploaded_by: string; uploaded_by_name?: string | null;
  confidence?: number | null; current_version?: number | null;
  created_at: string; updated_at: string;
};
type Extraction = {
  id: string; document_id: string; version: number; schema_id: string | null;
  fields: Record<string, any>; confidence_overall: number;
  confidence_per_field: Record<string, number>; llm_model: string | null;
  processing_time_ms: number | null; status: string; error: string | null; created_at: string;
};
type Review = {
  id: string; document_id: string; extraction_id: string; status: string;
  decision: string | null; notes: string | null; reviewed_at: string | null;
  reviewed_by: string | null; reviewed_by_name: string | null; created_at: string;
};
type DocumentDetail = DocumentSummary & { extractions: Extraction[]; reviews: Review[] };
type AuditLog = {
  id: string; user_id?: string | null; user_name?: string | null; action: string;
  resource_type?: string | null; resource_id?: string | null; resource_name?: string | null;
  details?: Record<string, any> | null; ip_address?: string | null; created_at: string;
};
type Analytics = {
  total_documents: number; by_status: Record<string, number>; by_type: Record<string, number>;
  avg_confidence: number; pending_review: number; avg_processing_seconds: number;
  last_7_days: { day: string; count: number }[];
  confidence_distribution: { high: number; medium: number; low: number };
};

// ─── Helpers ──────────────────────────────────────────────────────────────────
const prettyDate = (v?: string | null) => { if (!v) return "—"; try { return new Date(v).toLocaleString(); } catch { return v; } };
const shortDate  = (v?: string | null) => { if (!v) return "—"; try { return new Date(v).toLocaleDateString(); } catch { return v; } };
const fmtBytes   = (b?: number | null) => { if (b == null) return "—"; if (b < 1024) return `${b} B`; const k = b / 1024; return k < 1024 ? `${k.toFixed(1)} KB` : `${(k/1024).toFixed(1)} MB`; };

// ─── Status badge ─────────────────────────────────────────────────────────────
const SC: Record<string, [string, string, string]> = {
  extracted:    ["#ecfdf5","#065f46","#6ee7b7"],
  approved:     ["#ecfdf5","#065f46","#6ee7b7"],
  active:       ["#ecfdf5","#065f46","#6ee7b7"],
  completed:    ["#ecfdf5","#065f46","#6ee7b7"],
  needs_review: ["#fffbeb","#92400e","#fcd34d"],
  processing:   ["#eff6ff","#1e40af","#93c5fd"],
  pending:      ["#fffbeb","#92400e","#fcd34d"],
  error:        ["#fef2f2","#991b1b","#fca5a5"],
  rejected:     ["#fef2f2","#991b1b","#fca5a5"],
  failed:       ["#fef2f2","#991b1b","#fca5a5"],
  admin:        ["#eef2ff","#3730a3","#a5b4fc"],
  reviewer:     ["#f0fdf4","#166534","#86efac"],
  viewer:       ["#f8fafc","#475569","#cbd5e1"],
};
function Badge({ s }: { s: string }) {
  const [bg, tx, bd] = SC[s] || ["#f8fafc","#475569","#cbd5e1"];
  return <span style={{ background: bg, color: tx, border: `1px solid ${bd}`, padding: "2px 10px", borderRadius: 20, fontSize: 11, fontWeight: 700, whiteSpace: "nowrap", textTransform: "capitalize" }}>{s.replace(/_/g," ")}</span>;
}

// ─── UI atoms ─────────────────────────────────────────────────────────────────
const Card = ({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) =>
  <div style={{ background:"#fff", border:"1px solid #e2e8f0", borderRadius:16, overflow:"hidden", ...style }}>{children}</div>;

const CH = ({ title, right }: { title: string; right?: React.ReactNode }) =>
  <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"13px 18px", borderBottom:"1px solid #f1f5f9" }}>
    <span style={{ fontWeight:700, fontSize:14, color:"#0f172a" }}>{title}</span>
    {right}
  </div>;

const CB = ({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) =>
  <div style={{ padding:"16px 18px", ...style }}>{children}</div>;

function StatCard({ label, value, accent = "#6366f1" }: { label: string; value: React.ReactNode; accent?: string }) {
  return (
    <div style={{ background:"#f8fafc", border:"1px solid #e2e8f0", borderRadius:14, padding:"16px 20px", borderLeft:`4px solid ${accent}` }}>
      <div style={{ fontSize:11, color:"#94a3b8", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:8 }}>{label}</div>
      <div style={{ fontSize:28, fontWeight:800, color:"#0f172a", lineHeight:1 }}>{value}</div>
    </div>
  );
}

function Btn({ children, onClick, disabled, variant = "primary", style }: {
  children: React.ReactNode; onClick?: () => void; disabled?: boolean;
  variant?: "primary"|"secondary"|"danger"|"success"; style?: React.CSSProperties;
}) {
  const V = {
    primary:   { background:"#6366f1", color:"#fff", border:"none" },
    secondary: { background:"#fff",    color:"#374151", border:"1px solid #d1d5db" },
    danger:    { background:"#dc2626", color:"#fff", border:"none" },
    success:   { background:"#16a34a", color:"#fff", border:"none" },
  };
  return (
    <button onClick={onClick} disabled={disabled} style={{
      ...V[variant], borderRadius:10, padding:"9px 16px", fontSize:13, fontWeight:600,
      cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.6 : 1,
      fontFamily:"inherit", transition:"opacity 0.15s", ...style,
    }}>{children}</button>
  );
}

const Inp = ({ value, onChange, placeholder, type = "text", style }: {
  value: string; onChange: (v: string) => void; placeholder?: string; type?: string; style?: React.CSSProperties;
}) => <input type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
  style={{ width:"100%", border:"1px solid #d1d5db", borderRadius:10, padding:"10px 14px", fontSize:14, outline:"none", fontFamily:"inherit", boxSizing:"border-box", ...style }} />;

const Err  = ({ msg }: { msg: string }) => <div style={{ background:"#fef2f2", color:"#991b1b", border:"1px solid #fca5a5", padding:"10px 14px", borderRadius:10, fontSize:13, marginBottom:12 }}>{msg}</div>;
const Succ = ({ msg }: { msg: string }) => <div style={{ background:"#f0fdf4", color:"#166534", border:"1px solid #86efac", padding:"10px 14px", borderRadius:10, fontSize:13, marginBottom:12 }}>{msg}</div>;

// ─── Bar chart ────────────────────────────────────────────────────────────────
function BarChart({ data }: { data: { day: string; count: number }[] }) {
  if (!data.length) return <div style={{ color:"#94a3b8", fontSize:13, textAlign:"center", padding:24 }}>No data yet</div>;
  const max = Math.max(...data.map(d => d.count), 1);
  return (
    <div style={{ display:"flex", alignItems:"flex-end", gap:5, height:72 }}>
      {data.map((d, i) => (
        <div key={i} style={{ flex:1, display:"flex", flexDirection:"column", alignItems:"center", gap:4 }}>
          <div style={{ fontSize:10, color:"#6366f1", fontWeight:700 }}>{d.count || ""}</div>
          <div style={{ width:"100%", height: Math.max(4,(d.count/max)*52), background:"linear-gradient(180deg,#6366f1,#a5b4fc)", borderRadius:"4px 4px 0 0", transition:"height 0.4s" }} />
          <div style={{ color:"#94a3b8", fontSize:9 }}>{d.day?.slice(5)}</div>
        </div>
      ))}
    </div>
  );
}

// ─── Donut chart ──────────────────────────────────────────────────────────────
const PALETTE = ["#6366f1","#10b981","#f59e0b","#ef4444","#8b5cf6","#3b82f6","#ec4899","#14b8a6"];
function Donut({ data, alt }: { data: Record<string,number>; alt?: string[] }) {
  const C = alt || PALETTE;
  const entries = Object.entries(data).filter(([,v]) => v > 0);
  const total = entries.reduce((s,[,v]) => s+v, 0);
  if (!total) return <div style={{ color:"#94a3b8", fontSize:13, textAlign:"center", padding:16 }}>No data</div>;
  const r=34, cx=42, cy=42, sw=14, circ=2*Math.PI*r; let off=0;
  return (
    <div style={{ display:"flex", alignItems:"center", gap:16 }}>
      <svg width={84} height={84} viewBox="0 0 84 84" style={{ flexShrink:0 }}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#f1f5f9" strokeWidth={sw} />
        {entries.map(([,v],i) => {
          const pct=v/total, dash=pct*circ;
          const el=<circle key={i} cx={cx} cy={cy} r={r} fill="none" stroke={C[i%C.length]} strokeWidth={sw}
            strokeDasharray={`${dash} ${circ-dash}`} strokeDashoffset={-off*circ}
            style={{ transform:"rotate(-90deg)", transformOrigin:`${cx}px ${cy}px` }} />;
          off+=pct; return el;
        })}
        <text x={cx} y={cy+5} textAnchor="middle" fill="#0f172a" fontSize={13} fontWeight={700}>{total}</text>
      </svg>
      <div style={{ display:"flex", flexDirection:"column", gap:6, minWidth:0, flex:1 }}>
        {entries.map(([k,v],i) => (
          <div key={k} style={{ display:"flex", alignItems:"center", gap:7, fontSize:12 }}>
            <div style={{ width:8, height:8, borderRadius:"50%", background:C[i%C.length], flexShrink:0 }} />
            <span style={{ color:"#64748b", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", flex:1 }}>{k}</span>
            <span style={{ color:"#0f172a", fontWeight:700 }}>{v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Conf bar ─────────────────────────────────────────────────────────────────
function ConfBar({ label, value, total, color }: { label:string; value:number; total:number; color:string }) {
  return (
    <div>
      <div style={{ display:"flex", justifyContent:"space-between", fontSize:12, marginBottom:5 }}>
        <span style={{ color:"#64748b" }}>{label}</span><span style={{ color:"#0f172a", fontWeight:700 }}>{value}</span>
      </div>
      <div style={{ height:6, background:"#f1f5f9", borderRadius:4 }}>
        <div style={{ height:"100%", width:`${total?(value/total)*100:0}%`, background:color, borderRadius:4, transition:"width 0.5s" }} />
      </div>
    </div>
  );
}

// ─── Login ────────────────────────────────────────────────────────────────────
function LoginScreen({ onLogin }: { onLogin: (token: string, user: User) => void }) {
  const [email, setEmail] = useState("admin@docintel.ai");
  const [pass,  setPass]  = useState("Admin123!");
  const [err,   setErr]   = useState("");
  const [busy,  setBusy]  = useState(false);

  const go = async () => {
    setBusy(true); setErr("");
    try {
      const r = await fetch(`${API_BASE}/api/auth/login`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ email, password: pass }),
      });
      if (!r.ok) { const d = await r.json(); throw new Error(d.detail || "Login failed"); }
      const d = await r.json();
      onLogin(d.access_token, d.user);
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  };

  return (
    <div style={{ minHeight:"100vh", background:"#f8fafc", display:"flex", alignItems:"center", justifyContent:"center", fontFamily:"system-ui,sans-serif" }}>
      <div style={{ display:"grid", gridTemplateColumns:"1.1fr 0.9fr", gap:24, maxWidth:980, width:"100%", padding:24 }}>

        {/* Info panel */}
        <Card style={{ padding:40 }}>
          <div style={{ fontSize:13, color:"#6366f1", fontWeight:800, letterSpacing:"0.05em", marginBottom:10 }}>DOCINTEL</div>
          <h1 style={{ fontSize:30, fontWeight:800, color:"#0f172a", margin:"0 0 14px", lineHeight:1.2 }}>AI Document Intelligence Platform</h1>
          <p style={{ color:"#64748b", fontSize:14, lineHeight:1.8, marginBottom:28 }}>
            Upload contracts, invoices, and reports. Get structured AI extraction, confidence scores, human-in-the-loop review workflows, and a tamper-proof audit trail — all connected to VS Code via MCP.
          </p>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10, marginBottom:24 }}>
            {[
              ["🧠 AI Extraction",    "Structured fields from any PDF or doc"],
              ["✅ Review Workflow",   "Approve or reject with reviewer notes"],
              ["📋 Audit Trail",      "Every action timestamped and logged"],
              ["🔌 MCP Integration",  "7 tools live in VS Code Copilot"],
              ["📊 Analytics",        "Real-time dashboard with charts"],
              ["🔒 RBAC Security",    "Admin / reviewer / viewer roles"],
            ].map(([t,d]) => (
              <div key={t as string} style={{ background:"#f8fafc", border:"1px solid #e2e8f0", borderRadius:12, padding:"12px 14px" }}>
                <div style={{ fontWeight:700, fontSize:13, color:"#0f172a", marginBottom:3 }}>{t}</div>
                <div style={{ fontSize:12, color:"#64748b" }}>{d}</div>
              </div>
            ))}
          </div>
          <div style={{ background:"#f1f5f9", borderRadius:10, padding:"12px 16px", fontSize:12, color:"#64748b", lineHeight:1.8 }}>
            <strong style={{ color:"#374151" }}>Default credentials</strong><br/>
            admin@docintel.ai / Admin123! &nbsp;·&nbsp; <Badge s="admin" /><br/>
            reviewer@docintel.ai / Review123! &nbsp;·&nbsp; <Badge s="reviewer" />
          </div>
        </Card>

        {/* Login form */}
        <Card style={{ padding:40, display:"flex", flexDirection:"column", justifyContent:"center" }}>
          <h2 style={{ fontSize:24, fontWeight:800, color:"#0f172a", margin:"0 0 6px" }}>Sign in</h2>
          <p style={{ color:"#94a3b8", fontSize:13, marginBottom:28 }}>Access your DocIntel workspace</p>
          {err && <Err msg={err} />}
          <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
            <div>
              <label style={{ fontSize:13, fontWeight:600, color:"#374151", display:"block", marginBottom:6 }}>Email</label>
              <Inp value={email} onChange={setEmail} placeholder="you@example.com" />
            </div>
            <div>
              <label style={{ fontSize:13, fontWeight:600, color:"#374151", display:"block", marginBottom:6 }}>Password</label>
              <Inp value={pass} onChange={setPass} type="password" />
            </div>
            <Btn onClick={go} disabled={busy} style={{ padding:"13px", fontSize:14, marginTop:4 }}>
              {busy ? "Signing in…" : "Sign in →"}
            </Btn>
          </div>
          <div style={{ marginTop:24, padding:"14px 16px", background:"#f8fafc", borderRadius:10, fontSize:12, color:"#94a3b8", textAlign:"center" }}>
            Backend: <code style={{ color:"#6366f1" }}>{API_BASE}</code>
          </div>
        </Card>
      </div>
    </div>
  );
}

// ─── Docs table ───────────────────────────────────────────────────────────────
function DocsTable({ docs, onSelect, selectedId, showConf }: {
  docs: DocumentSummary[]; onSelect: (id:string) => void; selectedId?: string; showConf?: boolean;
}) {
  const cols = ["Name","Type","Status", showConf?"Confidence":null,"Uploaded"].filter(Boolean) as string[];
  return (
    <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
      <thead>
        <tr style={{ background:"#f8fafc", borderBottom:"1px solid #e2e8f0" }}>
          {cols.map(h => <th key={h} style={{ textAlign:"left", padding:"10px 16px", color:"#64748b", fontSize:11, fontWeight:700, textTransform:"uppercase", letterSpacing:"0.06em" }}>{h}</th>)}
        </tr>
      </thead>
      <tbody>
        {docs.map(d => (
          <tr key={d.id} onClick={() => onSelect(d.id)}
            style={{ borderBottom:"1px solid #f1f5f9", cursor:"pointer", background: selectedId===d.id ? "#eef2ff" : "transparent" }}
            onMouseEnter={e => { if (selectedId!==d.id) (e.currentTarget as HTMLElement).style.background="#f8fafc"; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = selectedId===d.id ? "#eef2ff" : "transparent"; }}>
            <td style={{ padding:"11px 16px", fontWeight:500, color:"#0f172a", maxWidth:200, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{d.name}</td>
            <td style={{ padding:"11px 16px", color:"#6366f1", fontSize:12 }}>{d.doc_type || "—"}</td>
            <td style={{ padding:"11px 16px" }}><Badge s={d.status} /></td>
            {showConf && <td style={{ padding:"11px 16px", color:"#64748b" }}>{d.confidence != null ? `${Math.round(d.confidence)}%` : "—"}</td>}
            <td style={{ padding:"11px 16px", color:"#94a3b8", whiteSpace:"nowrap" }}>{shortDate(d.created_at)}</td>
          </tr>
        ))}
        {!docs.length && <tr><td colSpan={cols.length} style={{ padding:"32px", textAlign:"center", color:"#94a3b8" }}>No documents yet — upload some above.</td></tr>}
      </tbody>
    </table>
  );
}

// ─── Detail panel ─────────────────────────────────────────────────────────────
function DetailPanel(p: {
  doc: DocumentDetail|null; loading: boolean; ext: Extraction|null;
  pdfUrl: string|null; pdfLoading: boolean;
  draftJson: string; setDraftJson: (v:string)=>void;
  notes: string; setNotes: (v:string)=>void;
  actionErr: string; actionMsg: string;
  saving: boolean; reviewing: "approved"|"rejected"|null;
  onSave:()=>void; onApprove:()=>void; onReject:()=>void;
  onDownload:()=>void; onDelete?:()=>void; onRefresh:()=>void;
}) {
  if (!p.doc && !p.loading) return (
    <Card><CH title="Document Details" />
      <CB><p style={{ color:"#94a3b8", fontSize:13 }}>Select a document from the table to inspect its details, extraction data, and review history.</p></CB>
    </Card>
  );
  const { doc } = p;
  return (
    <Card>
      <CH title={doc?.name || "Loading…"} right={p.loading ? <span style={{ fontSize:12, color:"#94a3b8" }}>Loading…</span> : null} />
      <CB>
        {p.actionMsg && <Succ msg={p.actionMsg} />}
        {p.actionErr && <Err  msg={p.actionErr} />}
        {doc && (
          <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
            {/* Meta */}
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:8 }}>
              {([["Type", doc.doc_type||"—"],["Status", doc.status],["Confidence",`${Math.round(doc.confidence??0)}%`],["Risk",doc.risk_level||"—"],["Pages",String(doc.page_count??0)],["Size",fmtBytes(doc.file_size)]] as [string,string][]).map(([l,v]) => (
                <div key={l} style={{ background:"#f8fafc", border:"1px solid #e2e8f0", borderRadius:10, padding:"10px 12px" }}>
                  <div style={{ fontSize:10, color:"#94a3b8", textTransform:"uppercase", letterSpacing:"0.08em" }}>{l}</div>
                  <div style={{ fontSize:13, fontWeight:600, color:"#0f172a", marginTop:3 }}>
                    {l==="Status"||l==="Risk" ? <Badge s={v} /> : v}
                  </div>
                </div>
              ))}
            </div>

            {/* PDF preview */}
            <div>
              <div style={{ fontSize:12, fontWeight:700, color:"#374151", marginBottom:8 }}>Document Preview</div>
              <div style={{ border:"1px solid #e2e8f0", borderRadius:10, overflow:"hidden", background:"#f8fafc", height:260 }}>
                {p.pdfLoading
                  ? <div style={{ display:"flex", alignItems:"center", justifyContent:"center", height:"100%", fontSize:13, color:"#94a3b8" }}>Loading preview…</div>
                  : p.pdfUrl
                    ? <iframe src={p.pdfUrl} style={{ width:"100%", height:"100%", border:"none" }} title="Preview" />
                    : <div style={{ display:"flex", alignItems:"center", justifyContent:"center", height:"100%", fontSize:13, color:"#94a3b8" }}>No preview available</div>}
              </div>
            </div>

            {/* Extraction */}
            {p.ext ? (
              <div>
                <div style={{ fontSize:12, fontWeight:700, color:"#374151", marginBottom:8 }}>
                  Extraction v{p.ext.version} &nbsp;·&nbsp; {p.ext.confidence_overall}% confidence &nbsp;·&nbsp; <span style={{ color:"#94a3b8" }}>{p.ext.llm_model||"—"}</span>
                </div>
                <textarea value={p.draftJson} onChange={e => p.setDraftJson(e.target.value)}
                  style={{ width:"100%", minHeight:180, border:"1px solid #d1d5db", borderRadius:10, padding:12, fontSize:12, fontFamily:"monospace", lineHeight:1.6, color:"#374151", boxSizing:"border-box", resize:"vertical" }} />
                <div style={{ display:"flex", gap:8, flexWrap:"wrap", marginTop:10 }}>
                  <Btn onClick={p.onSave}    disabled={p.saving}       variant="primary">  {p.saving             ? "Saving…"    : "Save fields"}</Btn>
                  <Btn onClick={p.onApprove} disabled={!!p.reviewing}  variant="success">  {p.reviewing==="approved" ? "Approving…" : "✓ Approve"}</Btn>
                  <Btn onClick={p.onReject}  disabled={!!p.reviewing}  variant="danger">   {p.reviewing==="rejected" ? "Rejecting…" : "✕ Reject"}</Btn>
                </div>
                <textarea value={p.notes} onChange={e => p.setNotes(e.target.value)} placeholder="Review notes (optional)…"
                  style={{ width:"100%", minHeight:60, border:"1px solid #d1d5db", borderRadius:10, padding:10, fontSize:13, fontFamily:"inherit", marginTop:8, boxSizing:"border-box", resize:"vertical" }} />
              </div>
            ) : (
              <div style={{ background:"#f8fafc", border:"1px solid #e2e8f0", borderRadius:10, padding:16, fontSize:13, color:"#94a3b8" }}>
                No extraction available yet. The document may still be processing.
              </div>
            )}

            {/* Reviews */}
            {(doc.reviews?.length > 0) && (
              <div>
                <div style={{ fontSize:12, fontWeight:700, color:"#374151", marginBottom:8 }}>Reviews ({doc.reviews.length})</div>
                {doc.reviews.map(r => (
                  <div key={r.id} style={{ background:"#f8fafc", border:"1px solid #e2e8f0", borderRadius:10, padding:"10px 14px", marginBottom:6 }}>
                    <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
                      <Badge s={r.decision||r.status} />
                      <span style={{ fontSize:11, color:"#94a3b8" }}>{prettyDate(r.created_at)}</span>
                    </div>
                    {r.notes && <div style={{ fontSize:12, color:"#64748b", marginTop:4 }}>{r.notes}</div>}
                    {r.reviewed_by_name && <div style={{ fontSize:11, color:"#94a3b8", marginTop:2 }}>by {r.reviewed_by_name}</div>}
                  </div>
                ))}
              </div>
            )}

            {/* Actions */}
            <div style={{ display:"flex", gap:8, flexWrap:"wrap", paddingTop:8, borderTop:"1px solid #f1f5f9" }}>
              <Btn onClick={p.onDownload} variant="secondary">↓ Download</Btn>
              <Btn onClick={p.onRefresh}  variant="secondary">↻ Refresh</Btn>
              {p.onDelete && <Btn onClick={p.onDelete} variant="danger">✕ Delete</Btn>}
            </div>
          </div>
        )}
      </CB>
    </Card>
  );
}

// ─── App ──────────────────────────────────────────────────────────────────────
const TABS = [
  { id:"dashboard", label:"Dashboard"  },
  { id:"documents", label:"Documents"  },
  { id:"schemas",   label:"Schemas"    },
  { id:"audit",     label:"Audit Logs" },
  { id:"admin",     label:"Admin", adminOnly:true },
];

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem("di_token")||"");
  const [me,    setMe]    = useState<User|null>(() => { try { return JSON.parse(localStorage.getItem("di_user")||"null"); } catch { return null; } });

  const [tab,         setTab]         = useState("dashboard");
  const [docs,        setDocs]        = useState<DocumentSummary[]>([]);
  const [schemas,     setSchemas]     = useState<SchemaSummary[]>([]);
  const [users,       setUsers]       = useState<User[]>([]);
  const [auditLogs,   setAuditLogs]   = useState<AuditLog[]>([]);
  const [analytics,   setAnalytics]   = useState<Analytics|null>(null);
  const [selectedDoc, setSelectedDoc] = useState<DocumentDetail|null>(null);

  const [loading,     setLoading]     = useState(false);
  const [loadErr,     setLoadErr]     = useState("");
  const [selLoading,  setSelLoading]  = useState(false);
  const [actErr,      setActErr]      = useState("");
  const [actMsg,      setActMsg]      = useState("");

  const [uploadFiles, setUploadFiles] = useState<FileList|null>(null);
  const [schemaId,    setSchemaId]    = useState("");
  const [uploading,   setUploading]   = useState(false);
  const [uploadErr,   setUploadErr]   = useState("");

  const [draftJson,   setDraftJson]   = useState("{}");
  const [notes,       setNotes]       = useState("");
  const [saving,      setSaving]      = useState(false);
  const [reviewing,   setReviewing]   = useState<"approved"|"rejected"|null>(null);

  const [pdfUrl,      setPdfUrl]      = useState<string|null>(null);
  const [pdfLoading,  setPdfLoading]  = useState(false);
  const [docSearch,   setDocSearch]   = useState("");
  const [auditSearch, setAuditSearch] = useState("");

  const ext = selectedDoc?.extractions?.[0] || null;

  // Auth fetch
  const af = useCallback(async (path: string, init: RequestInit = {}) => {
    const h = new Headers(init.headers||{});
    if (token) h.set("Authorization", `Bearer ${token}`);
    const r = await fetch(`${API_BASE}${path}`, { ...init, headers:h });
    if (r.status===401) { localStorage.removeItem("di_token"); setToken(""); setMe(null); }
    return r;
  }, [token]);

  // Load all
  const loadAll = useCallback(async () => {
    if (!token) return;
    setLoading(true); setLoadErr("");
    try {
      const [dr, sr, ar, anr] = await Promise.all([
        af("/api/documents/?limit=100"),
        af("/api/schemas/"),
        af("/api/audit/?limit=100"),
        af("/api/analytics/overview"),
      ]);
      if (dr.ok)  { const d = await dr.json();  setDocs(d.documents || []); }
      if (sr.ok)  { setSchemas(await sr.json()); }
      if (ar.ok)  { const d = await ar.json();  setAuditLogs(d.logs || []); }   // ← key is "logs"
      if (anr.ok) { setAnalytics(await anr.json()); }
      if (me?.role === "admin") {
        const ur = await af("/api/users/");
        if (ur.ok) setUsers(await ur.json());   // ← returns plain array
      }
    } catch { setLoadErr("Cannot reach backend at " + API_BASE + ". Is it running?"); }
    finally { setLoading(false); }
  }, [token, af, me?.role]);

  useEffect(() => {
    if (token) { loadAll(); const t = setInterval(loadAll, 15000); return () => clearInterval(t); }
  }, [token]);

  // Load doc detail
  const loadDoc = async (id: string) => {
    setSelLoading(true); setActErr(""); setActMsg("");
    try {
      const r = await af(`/api/documents/${id}`);
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      setSelectedDoc(d);
      setDraftJson(JSON.stringify(d.extractions?.[0]?.fields ?? {}, null, 2));
      setNotes("");
    } catch (e: any) { setActErr(e.message); }
    finally { setSelLoading(false); }
  };

  // PDF preview
  useEffect(() => {
    if (!selectedDoc) { setPdfUrl(null); return; }
    setPdfLoading(true);
    af(`/api/documents/${selectedDoc.id}/download`)
      .then(async r => {
        if (!r.ok) { setPdfUrl(null); return; }
        const blob = await r.blob();
        setPdfUrl(prev => { if (prev) URL.revokeObjectURL(prev); return URL.createObjectURL(blob); });
      })
      .catch(() => setPdfUrl(null))
      .finally(() => setPdfLoading(false));
  }, [selectedDoc?.id]);

  // Upload
  const upload = async () => {
    if (!uploadFiles?.length) { setUploadErr("Choose at least one file."); return; }
    setUploading(true); setUploadErr("");
    try {
      const form = new FormData();
      Array.from(uploadFiles).forEach(f => form.append("files", f));
      if (schemaId.trim()) form.append("schema_id", schemaId.trim());
      const r = await af("/api/documents/", { method:"POST", body:form });
      if (!r.ok) throw new Error(await r.text());
      setUploadFiles(null); setSchemaId(""); await loadAll();
    } catch (e: any) { setUploadErr(e.message); }
    finally { setUploading(false); }
  };

  // Save extraction fields
  const saveFields = async () => {
    if (!selectedDoc || !ext) return;
    setSaving(true); setActErr(""); setActMsg("");
    try {
      const parsed = JSON.parse(draftJson);
      const r = await af(`/api/extractions/${ext.id}/fields`, {
        method:"PATCH", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ fields: parsed }),
      });
      if (!r.ok) throw new Error(await r.text());
      setActMsg("Fields saved successfully."); await loadDoc(selectedDoc.id); await loadAll();
    } catch (e: any) { setActErr(e.message || "Invalid JSON — check syntax."); }
    finally { setSaving(false); }
  };

  // Review
  const review = async (decision: "approved"|"rejected") => {
    if (!selectedDoc) return;
    setReviewing(decision); setActErr(""); setActMsg("");
    try {
      const r = await af(`/api/documents/${selectedDoc.id}/review`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ decision, notes: notes.trim()||null, extraction_id: ext?.id||null }),
      });
      if (!r.ok) throw new Error(await r.text());
      setActMsg(`Document ${decision}.`); await loadDoc(selectedDoc.id); await loadAll();
    } catch (e: any) { setActErr(e.message); }
    finally { setReviewing(null); }
  };

  // Download
  const dlDoc = async () => {
    if (!selectedDoc) return;
    try {
      const r = await af(`/api/documents/${selectedDoc.id}/download`);
      if (!r.ok) throw new Error(await r.text());
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href=url; a.download=selectedDoc.original_name||selectedDoc.name; a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) { setActErr(e.message); }
  };

  // Delete
  const delDoc = async () => {
    if (!selectedDoc || !window.confirm(`Delete "${selectedDoc.name}"? This cannot be undone.`)) return;
    setActErr(""); setActMsg("");
    try {
      const r = await af(`/api/documents/${selectedDoc.id}`, { method:"DELETE" });
      if (!r.ok) throw new Error(await r.text());
      setSelectedDoc(null); setActMsg("Document deleted."); await loadAll();
    } catch (e: any) { setActErr(e.message); }
  };

  const totals = useMemo(() => ({
    total:    docs.length,
    done:     docs.filter(d => d.status==="extracted"||d.status==="approved").length,
    review:   docs.filter(d => d.status==="needs_review").length,
    avgConf:  docs.length ? Math.round(docs.reduce((s,d) => s+(d.confidence||0),0)/docs.length) : 0,
  }), [docs]);

  const filteredDocs = useMemo(() =>
    docs.filter(d => !docSearch || d.name?.toLowerCase().includes(docSearch.toLowerCase()) || (d.doc_type||"").toLowerCase().includes(docSearch.toLowerCase())),
    [docs, docSearch]);

  const filteredLogs = useMemo(() =>
    auditLogs.filter(l => !auditSearch || l.action?.toLowerCase().includes(auditSearch.toLowerCase()) || (l.user_name||"").toLowerCase().includes(auditSearch.toLowerCase()) || (l.resource_name||"").toLowerCase().includes(auditSearch.toLowerCase())),
    [auditLogs, auditSearch]);

  // Login gate
  if (!token) return <LoginScreen onLogin={(t,u) => { localStorage.setItem("di_token",t); localStorage.setItem("di_user",JSON.stringify(u)); setToken(t); setMe(u); }} />;

  const visibleTabs = TABS.filter(t => !t.adminOnly || me?.role==="admin");

  return (
    <div style={{ minHeight:"100vh", background:"#f8fafc", fontFamily:"system-ui,sans-serif" }}>
      {/* ── Header ── */}
      <header style={{ background:"#fff", borderBottom:"1px solid #e2e8f0", padding:"0 28px", position:"sticky", top:0, zIndex:100, boxShadow:"0 1px 3px #0000000a" }}>
        <div style={{ maxWidth:1440, margin:"0 auto", display:"flex", alignItems:"center", justifyContent:"space-between", height:60 }}>
          <div style={{ display:"flex", alignItems:"center", gap:28 }}>
            <div style={{ fontWeight:900, fontSize:18, color:"#6366f1", letterSpacing:"-0.02em" }}>DocIntel</div>
            <nav style={{ display:"flex", gap:2 }}>
              {visibleTabs.map(t => (
                <button key={t.id} onClick={() => setTab(t.id)} style={{
                  background: tab===t.id ? "#eef2ff" : "transparent",
                  color:      tab===t.id ? "#6366f1" : "#64748b",
                  border:"none", borderRadius:8, padding:"7px 14px",
                  fontSize:13, fontWeight: tab===t.id ? 700 : 500,
                  cursor:"pointer", fontFamily:"inherit",
                }}>{t.label}</button>
              ))}
            </nav>
          </div>
          <div style={{ display:"flex", alignItems:"center", gap:10 }}>
            {loading && <span style={{ fontSize:12, color:"#94a3b8" }}>↻ Refreshing…</span>}
            <Btn onClick={loadAll} variant="secondary" style={{ padding:"6px 14px", fontSize:13 }}>↻ Refresh</Btn>
            <div style={{ display:"flex", alignItems:"center", gap:8, fontSize:13, color:"#64748b" }}>
              <div style={{ width:32, height:32, borderRadius:"50%", background:"#eef2ff", display:"flex", alignItems:"center", justifyContent:"center", fontWeight:700, fontSize:12, color:"#6366f1" }}>
                {me?.name?.split(" ").map(w=>w[0]).join("").slice(0,2).toUpperCase()}
              </div>
              {me?.name} &nbsp;<Badge s={me?.role||""} />
            </div>
            <Btn variant="secondary" style={{ padding:"6px 14px", fontSize:13 }} onClick={() => {
              localStorage.removeItem("di_token"); localStorage.removeItem("di_user"); setToken(""); setMe(null);
            }}>Sign out</Btn>
          </div>
        </div>
      </header>

      <div style={{ maxWidth:1440, margin:"0 auto", padding:"24px 28px" }}>
        {loadErr && <Err msg={loadErr} />}

        {/* ════ DASHBOARD ════ */}
        {tab==="dashboard" && (
          <div style={{ display:"flex", flexDirection:"column", gap:20 }}>
            {/* Stats */}
            <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:16 }}>
              <StatCard label="Total Documents"  value={analytics?.total_documents ?? totals.total} accent="#6366f1" />
              <StatCard label="Pending Review"   value={analytics?.pending_review  ?? totals.review} accent="#f59e0b" />
              <StatCard label="Avg Confidence"   value={`${analytics?.avg_confidence ?? totals.avgConf}%`} accent="#10b981" />
              <StatCard label="Avg Processing"   value={analytics ? `${analytics.avg_processing_seconds}s` : "—"} accent="#8b5cf6" />
            </div>

            {/* Charts */}
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:16 }}>
              <Card><CH title="Documents — Last 7 Days" /><CB><BarChart data={analytics?.last_7_days||[]} /></CB></Card>
              <Card><CH title="By Status" /><CB><Donut data={analytics?.by_status||{}} /></CB></Card>
              <Card><CH title="By Document Type" /><CB><Donut data={analytics?.by_type||{}} alt={["#10b981","#3b82f6","#f59e0b","#ef4444","#8b5cf6"]} /></CB></Card>
            </div>

            {/* Conf + recent docs */}
            <div style={{ display:"grid", gridTemplateColumns:"300px 1fr", gap:16 }}>
              <Card>
                <CH title="Confidence Distribution" />
                <CB>
                  {analytics ? (() => {
                    const t = (analytics.confidence_distribution.high + analytics.confidence_distribution.medium + analytics.confidence_distribution.low)||1;
                    return (
                      <div style={{ display:"flex", flexDirection:"column", gap:14 }}>
                        <ConfBar label="High ≥90%"    value={analytics.confidence_distribution.high}   total={t} color="#10b981" />
                        <ConfBar label="Medium 70–89%" value={analytics.confidence_distribution.medium} total={t} color="#f59e0b" />
                        <ConfBar label="Low <70%"      value={analytics.confidence_distribution.low}    total={t} color="#ef4444" />
                      </div>
                    );
                  })() : <div style={{ color:"#94a3b8", fontSize:13 }}>No data yet</div>}
                </CB>
              </Card>
              <Card>
                <CH title="Recent Documents" right={<span style={{ fontSize:12, color:"#94a3b8" }}>{docs.length} total</span>} />
                <DocsTable docs={docs.slice(0,8)} onSelect={id => { loadDoc(id); setTab("documents"); }} selectedId={selectedDoc?.id} />
              </Card>
            </div>
          </div>
        )}

        {/* ════ DOCUMENTS ════ */}
        {tab==="documents" && (
          <div style={{ display:"grid", gridTemplateColumns:"1fr 420px", gap:20, alignItems:"start" }}>
            <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
              {/* Upload */}
              <Card>
                <CH title="Upload Documents" />
                <CB>
                  <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr auto", gap:12, alignItems:"end" }}>
                    <div>
                      <label style={{ fontSize:12, fontWeight:600, color:"#374151", display:"block", marginBottom:6 }}>Files</label>
                      <input type="file" multiple accept=".pdf,.docx,.xlsx,.jpg,.jpeg,.png,.txt,.csv"
                        onChange={e => setUploadFiles(e.target.files)}
                        style={{ width:"100%", border:"1px solid #d1d5db", borderRadius:10, padding:"8px 12px", fontSize:13, background:"#fff", boxSizing:"border-box" }} />
                    </div>
                    <div>
                      <label style={{ fontSize:12, fontWeight:600, color:"#374151", display:"block", marginBottom:6 }}>Schema ID (optional)</label>
                      <Inp value={schemaId} onChange={setSchemaId} placeholder="Leave blank to auto-classify" />
                    </div>
                    <Btn onClick={upload} disabled={uploading} style={{ whiteSpace:"nowrap", alignSelf:"flex-end" }}>
                      {uploading ? "Uploading…" : "↑ Upload"}
                    </Btn>
                  </div>
                  {uploadErr && <div style={{ marginTop:10 }}><Err msg={uploadErr} /></div>}
                </CB>
              </Card>

              {/* List */}
              <Card>
                <CH title="All Documents"
                  right={<Inp value={docSearch} onChange={setDocSearch} placeholder="Search name or type…" style={{ width:220, padding:"6px 12px", fontSize:13 }} />} />
                <DocsTable docs={filteredDocs} onSelect={loadDoc} selectedId={selectedDoc?.id} showConf />
              </Card>
            </div>

            <DetailPanel
              doc={selectedDoc} loading={selLoading} ext={ext}
              pdfUrl={pdfUrl} pdfLoading={pdfLoading}
              draftJson={draftJson} setDraftJson={setDraftJson}
              notes={notes} setNotes={setNotes}
              actionErr={actErr} actionMsg={actMsg}
              saving={saving} reviewing={reviewing}
              onSave={saveFields} onApprove={() => review("approved")} onReject={() => review("rejected")}
              onDownload={dlDoc} onDelete={me?.role==="admin" ? delDoc : undefined}
              onRefresh={() => selectedDoc && loadDoc(selectedDoc.id)}
            />
          </div>
        )}

        {/* ════ SCHEMAS ════ */}
        {tab==="schemas" && (
          <Card>
            <CH title="Extraction Schemas" right={<span style={{ fontSize:12, color:"#94a3b8" }}>{schemas.length} schemas</span>} />
            <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
              <thead>
                <tr style={{ background:"#f8fafc", borderBottom:"1px solid #e2e8f0" }}>
                  {["Name","Doc Type","Version","Status","Documents","Created"].map(h =>
                    <th key={h} style={{ textAlign:"left", padding:"10px 16px", color:"#64748b", fontSize:11, fontWeight:700, textTransform:"uppercase", letterSpacing:"0.06em" }}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {schemas.map(s => (
                  <tr key={s.id} style={{ borderBottom:"1px solid #f1f5f9" }}>
                    <td style={{ padding:"12px 16px", fontWeight:600, color:"#0f172a" }}>{s.name}</td>
                    <td style={{ padding:"12px 16px", color:"#6366f1", fontSize:12 }}>{s.doc_type}</td>
                    <td style={{ padding:"12px 16px", color:"#64748b" }}>v{s.version}</td>
                    <td style={{ padding:"12px 16px" }}><Badge s={s.status} /></td>
                    <td style={{ padding:"12px 16px", color:"#64748b" }}>{s.doc_count}</td>
                    <td style={{ padding:"12px 16px", color:"#94a3b8", fontSize:12 }}>{shortDate(s.created_at)}</td>
                  </tr>
                ))}
                {!schemas.length && <tr><td colSpan={6} style={{ padding:"32px", textAlign:"center", color:"#94a3b8" }}>No schemas found</td></tr>}
              </tbody>
            </table>
          </Card>
        )}

        {/* ════ AUDIT ════ */}
        {tab==="audit" && (
          <Card>
            <CH title="Audit Logs"
              right={<Inp value={auditSearch} onChange={setAuditSearch} placeholder="Search action, user…" style={{ width:240, padding:"6px 12px", fontSize:13 }} />} />
            <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
              <thead>
                <tr style={{ background:"#f8fafc", borderBottom:"1px solid #e2e8f0" }}>
                  {["Action","User","Resource","IP Address","Timestamp"].map(h =>
                    <th key={h} style={{ textAlign:"left", padding:"10px 16px", color:"#64748b", fontSize:11, fontWeight:700, textTransform:"uppercase", letterSpacing:"0.06em" }}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map(l => (
                  <tr key={l.id} style={{ borderBottom:"1px solid #f1f5f9" }}>
                    <td style={{ padding:"10px 16px" }}>
                      <code style={{ background:"#eef2ff", color:"#4338ca", padding:"2px 8px", borderRadius:6, fontSize:11, fontWeight:700 }}>{l.action}</code>
                    </td>
                    <td style={{ padding:"10px 16px", color:"#374151" }}>{l.user_name||"—"}</td>
                    <td style={{ padding:"10px 16px", color:"#64748b", fontSize:12 }}>
                      {l.resource_type||"—"}{l.resource_name ? ` · ${l.resource_name}` : ""}
                    </td>
                    <td style={{ padding:"10px 16px", color:"#94a3b8", fontSize:12, fontFamily:"monospace" }}>{l.ip_address||"—"}</td>
                    <td style={{ padding:"10px 16px", color:"#94a3b8", fontSize:12, whiteSpace:"nowrap" }}>{prettyDate(l.created_at)}</td>
                  </tr>
                ))}
                {!filteredLogs.length && <tr><td colSpan={5} style={{ padding:"32px", textAlign:"center", color:"#94a3b8" }}>No audit logs found</td></tr>}
              </tbody>
            </table>
          </Card>
        )}

        {/* ════ ADMIN ════ */}
        {tab==="admin" && me?.role==="admin" && (
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:20 }}>
            {/* Users */}
            <Card>
              <CH title="Users" right={<span style={{ fontSize:12, color:"#94a3b8" }}>{users.length} users</span>} />
              <CB style={{ padding:0 }}>
                {users.map(u => (
                  <div key={u.id} style={{ padding:"14px 18px", borderBottom:"1px solid #f1f5f9", display:"flex", alignItems:"center", gap:14 }}>
                    <div style={{ width:38, height:38, borderRadius:"50%", background:"#eef2ff", display:"flex", alignItems:"center", justifyContent:"center", fontWeight:800, fontSize:13, color:"#6366f1", flexShrink:0 }}>
                      {u.avatar_initials || u.name?.split(" ").map(w=>w[0]).join("").slice(0,2).toUpperCase()}
                    </div>
                    <div style={{ flex:1, minWidth:0 }}>
                      <div style={{ fontWeight:700, fontSize:14, color:"#0f172a" }}>{u.name}</div>
                      <div style={{ fontSize:12, color:"#64748b" }}>{u.email}</div>
                      {u.department && <div style={{ fontSize:11, color:"#94a3b8" }}>{u.department}</div>}
                    </div>
                    <div style={{ display:"flex", flexDirection:"column", alignItems:"flex-end", gap:4 }}>
                      <Badge s={u.role} />
                      <span style={{ fontSize:11, color:"#94a3b8" }}>{shortDate(u.created_at)}</span>
                    </div>
                  </div>
                ))}
                {!users.length && <CB><p style={{ color:"#94a3b8", fontSize:13 }}>No users loaded</p></CB>}
              </CB>
            </Card>

            {/* System info */}
            <Card>
              <CH title="System Information" />
              <CB>
                <div style={{ display:"flex", flexDirection:"column", gap:0, fontSize:13 }}>
                  {[
                    ["API Base",       API_BASE],
                    ["Auth Token",     token ? "Active ✓" : "Missing ✗"],
                    ["Auto Refresh",   "Every 15 seconds"],
                    ["Total Documents",String(docs.length)],
                    ["Schemas",        String(schemas.length)],
                    ["Users",          String(users.length)],
                    ["MCP Tools",      "7 tools — VS Code Copilot"],
                    ["Backend",        "FastAPI + PostgreSQL + Redis"],
                    ["Frontend",       "React + Vite + TypeScript"],
                    ["Worker",         "Celery (background AI processing)"],
                  ].map(([k,v]) => (
                    <div key={k} style={{ display:"flex", justifyContent:"space-between", padding:"10px 0", borderBottom:"1px solid #f1f5f9" }}>
                      <span style={{ color:"#64748b" }}>{k}</span>
                      <span style={{ color:"#0f172a", fontWeight:600, fontFamily: k==="API Base"?"monospace":"inherit", fontSize: k==="API Base"?12:13 }}>{v}</span>
                    </div>
                  ))}
                </div>
              </CB>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}

