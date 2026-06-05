import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  deleteDocument,
  getCurrentEmployee,
  listDocuments,
  loginEmployee,
  queryKnowledgeBase,
  queryKnowledgeBaseForEmployee,
  registerEmployee,
  logoutEmployee,
  uploadDocument,
} from "./services/api";
import type { DocumentMetadata, QueryResponse, UserProfile } from "./types";

const EMPLOYEE_TOKEN_KEY = "navigator.employee.token";
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function App() {
  const [portal, setPortal] = useState<"employee" | "admin">("employee");

  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [sourceUrl, setSourceUrl] = useState("");
  const [question, setQuestion] = useState("");
  const [queryResult, setQueryResult] = useState<QueryResponse | null>(null);

  const [employeeToken, setEmployeeToken] = useState<string | null>(null);
  const [employeeUser, setEmployeeUser] = useState<UserProfile | null>(null);
  const [employeeQuestion, setEmployeeQuestion] = useState("");
  const [employeeQueryResult, setEmployeeQueryResult] = useState<QueryResponse | null>(null);
  const [loginIdentifier, setLoginIdentifier] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [registerUsername, setRegisterUsername] = useState("");
  const [registerEmail, setRegisterEmail] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [busyState, setBusyState] = useState<"idle" | "uploading" | "deleting" | "querying">("idle");
  const [employeeBusyState, setEmployeeBusyState] = useState<"idle" | "registering" | "logging-in" | "querying" | "logging-out">("idle");

  const showError = (message: string): void => {
    setStatusMessage(null);
    setError(message);
  };

  const showSuccess = (message: string): void => {
    setError(null);
    setStatusMessage(message);
  };

  const isBusy = busyState !== "idle";
  const isEmployeeBusy = employeeBusyState !== "idle";
  const hasDocuments = useMemo(() => documents.length > 0, [documents.length]);
  const canRegister = registerUsername.trim().length >= 2 && EMAIL_PATTERN.test(registerEmail.trim()) && registerPassword.length >= 8;
  const canLogin = loginIdentifier.trim().length >= 2 && loginPassword.length >= 8;

  useEffect(() => {
    void refreshDocuments();
    void restoreEmployeeSession();
  }, []);

  async function restoreEmployeeSession(): Promise<void> {
    const token = localStorage.getItem(EMPLOYEE_TOKEN_KEY);
    if (!token) {
      return;
    }

    try {
      const user = await getCurrentEmployee(token);
      setEmployeeToken(token);
      setEmployeeUser(user);
    } catch {
      localStorage.removeItem(EMPLOYEE_TOKEN_KEY);
      setEmployeeToken(null);
      setEmployeeUser(null);
    }
  }

  async function refreshDocuments(): Promise<void> {
    try {
      const response = await listDocuments();
      setDocuments(response.documents);
    } catch (err) {
      showError(err instanceof Error ? err.message : "Unable to load documents.");
    }
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const trimmedUrl = sourceUrl.trim();
    if (!selectedFile && !trimmedUrl) {
      showError("Choose a PDF or provide a source URL before uploading.");
      return;
    }

    setError(null);
    setStatusMessage(null);
    setBusyState("uploading");
    try {
      const uploadedName = selectedFile?.name ?? trimmedUrl;
      await uploadDocument(selectedFile, trimmedUrl || undefined);
      setSelectedFile(null);
      setSourceUrl("");
      await refreshDocuments();
      showSuccess(`Uploaded "${uploadedName}" successfully.`);
    } catch (err) {
      showError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusyState("idle");
    }
  }

  async function handleDelete(documentId: string): Promise<void> {
    setError(null);
    setStatusMessage(null);
    setBusyState("deleting");
    try {
      await deleteDocument(documentId);
      await refreshDocuments();
      showSuccess("Document deleted successfully.");
    } catch (err) {
      showError(err instanceof Error ? err.message : "Delete failed.");
    } finally {
      setBusyState("idle");
    }
  }

  async function handleQuery(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!question.trim()) {
      showError("Enter a question to test retrieval.");
      return;
    }

    setError(null);
    setStatusMessage(null);
    setBusyState("querying");
    try {
      const response = await queryKnowledgeBase({ question: question.trim() });
      setQueryResult(response);
    } catch (err) {
      showError(err instanceof Error ? err.message : "Query failed.");
    } finally {
      setBusyState("idle");
    }
  }

  async function handleRegister(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!registerUsername.trim()) {
      showError("Please enter your user name to register.");
      return;
    }
    if (registerUsername.trim().length < 2) {
      showError("User name must be at least 2 characters.");
      return;
    }
    if (!registerEmail.trim()) {
      showError("Please enter your email to register.");
      return;
    }
    if (!EMAIL_PATTERN.test(registerEmail.trim())) {
      showError("Please enter a valid email address.");
      return;
    }
    if (!registerPassword) {
      showError("Please enter your password to register.");
      return;
    }
    if (registerPassword.length < 8) {
      showError("Password must be at least 8 characters.");
      return;
    }

    setStatusMessage(null);
    setError(null);
    setEmployeeBusyState("registering");

    try {
      const response = await registerEmployee({
        username: registerUsername.trim(),
        email: registerEmail.trim(),
        password: registerPassword,
      });
      localStorage.setItem(EMPLOYEE_TOKEN_KEY, response.token);
      setEmployeeToken(response.token);
      setEmployeeUser(response.user);
      setRegisterUsername("");
      setRegisterEmail("");
      setRegisterPassword("");
      showSuccess("Registered and logged in successfully.");
    } catch (err) {
      showError(err instanceof Error ? err.message : "Registration failed.");
    } finally {
      setEmployeeBusyState("idle");
    }
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!loginIdentifier.trim()) {
      showError("Please enter your user name or email to login.");
      return;
    }
    if (loginIdentifier.trim().length < 2) {
      showError("User name or email must be at least 2 characters.");
      return;
    }
    if (!loginPassword) {
      showError("Please enter your password to login.");
      return;
    }
    if (loginPassword.length < 8) {
      showError("Password must be at least 8 characters.");
      return;
    }

    setStatusMessage(null);
    setError(null);
    setEmployeeBusyState("logging-in");

    try {
      const response = await loginEmployee({ identifier: loginIdentifier.trim(), password: loginPassword });
      localStorage.setItem(EMPLOYEE_TOKEN_KEY, response.token);
      setEmployeeToken(response.token);
      setEmployeeUser(response.user);
      setLoginPassword("");
      showSuccess("Logged in successfully.");
    } catch (err) {
      showError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setEmployeeBusyState("idle");
    }
  }

  async function handleLogout(): Promise<void> {
    if (!employeeToken) {
      return;
    }

    setEmployeeBusyState("logging-out");
    try {
      await logoutEmployee(employeeToken);
    } catch {
      // Ignore logout errors and clear local session anyway.
    } finally {
      localStorage.removeItem(EMPLOYEE_TOKEN_KEY);
      setEmployeeToken(null);
      setEmployeeUser(null);
      setEmployeeQueryResult(null);
      setEmployeeBusyState("idle");
      showSuccess("Logged out successfully.");
    }
  }

  async function handleEmployeeQuery(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!employeeToken) {
      showError("Please log in to ask questions.");
      return;
    }
    if (!employeeQuestion.trim()) {
      showError("Enter a question.");
      return;
    }

    setStatusMessage(null);
    setError(null);
    setEmployeeBusyState("querying");
    try {
      const response = await queryKnowledgeBaseForEmployee(employeeToken, { question: employeeQuestion.trim() });
      setEmployeeQueryResult(response);
    } catch (err) {
      showError(err instanceof Error ? err.message : "Employee query failed.");
    } finally {
      setEmployeeBusyState("idle");
    }
  }

  return (
    <main className="min-h-screen bg-slate-100 p-6">
      <div className="mx-auto max-w-5xl space-y-6">
        <header className="rounded-xl bg-white p-6 shadow-sm">
          <h1 className="text-2xl font-semibold text-slate-900">Navigator</h1>
          <p className="mt-2 text-sm text-slate-600">
            Employee login and RAG Q&A with an admin interface for document ingestion.
          </p>
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={() => setPortal("employee")}
              className={`rounded-md px-3 py-1 text-sm ${portal === "employee" ? "bg-slate-900 text-white" : "border border-slate-300 text-slate-700"}`}
            >
              Employee Portal
            </button>
            <button
              type="button"
              onClick={() => setPortal("admin")}
              className={`rounded-md px-3 py-1 text-sm ${portal === "admin" ? "bg-slate-900 text-white" : "border border-slate-300 text-slate-700"}`}
            >
              Admin Console
            </button>
          </div>
        </header>

        {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
        {statusMessage && <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">{statusMessage}</div>}

        {portal === "employee" ? (
          <section className="space-y-6">
            {!employeeToken || !employeeUser ? (
              <div className="grid gap-6 md:grid-cols-2">
                <form onSubmit={(event) => void handleRegister(event)} className="rounded-xl bg-white p-5 shadow-sm">
                  <h2 className="text-lg font-medium text-slate-900">Register</h2>
                  <div className="mt-3 space-y-3">
                    <input
                      type="text"
                      value={registerUsername}
                      onChange={(event) => setRegisterUsername(event.target.value)}
                      placeholder="User Name"
                      required
                      minLength={2}
                      className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                    />
                    <input
                      type="email"
                      value={registerEmail}
                      onChange={(event) => setRegisterEmail(event.target.value)}
                      placeholder="Email"
                      required
                      className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                    />
                    <input
                      type="password"
                      value={registerPassword}
                      onChange={(event) => setRegisterPassword(event.target.value)}
                      placeholder="Password"
                      required
                      minLength={8}
                      className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={isEmployeeBusy || !canRegister}
                    className="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                  >
                    {employeeBusyState === "registering" ? "Registering..." : "Register"}
                  </button>
                </form>

                <form onSubmit={(event) => void handleLogin(event)} className="rounded-xl bg-white p-5 shadow-sm">
                  <h2 className="text-lg font-medium text-slate-900">Login</h2>
                  <div className="mt-3 space-y-3">
                    <input
                      type="text"
                      value={loginIdentifier}
                      onChange={(event) => setLoginIdentifier(event.target.value)}
                      placeholder="User Name or Email"
                      required
                      className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                    />
                    <input
                      type="password"
                      value={loginPassword}
                      onChange={(event) => setLoginPassword(event.target.value)}
                      placeholder="Password"
                      required
                      minLength={8}
                      className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={isEmployeeBusy || !canLogin}
                    className="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                  >
                    {employeeBusyState === "logging-in" ? "Logging in..." : "Login"}
                  </button>
                </form>
              </div>
            ) : (
              <>
                <div className="rounded-xl bg-white p-5 shadow-sm">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-lg font-medium text-slate-900">Welcome</h2>
                      <p className="text-sm text-slate-600">Logged in as {employeeUser.username}</p>
                      <p className="text-xs text-slate-500">{employeeUser.email}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleLogout()}
                      disabled={isEmployeeBusy}
                      className="rounded-md border border-slate-300 px-3 py-1 text-sm text-slate-700 disabled:opacity-50"
                    >
                      {employeeBusyState === "logging-out" ? "Logging out..." : "Logout"}
                    </button>
                  </div>
                </div>

                <section className="rounded-xl bg-white p-5 shadow-sm">
                  <h2 className="text-lg font-medium text-slate-900">Ask Questions</h2>
                  <p className="mt-1 text-sm text-slate-600">Ask questions across uploaded documents using RAG.</p>
                  <form onSubmit={(event) => void handleEmployeeQuery(event)} className="mt-3 flex flex-col gap-3">
                    <textarea
                      value={employeeQuestion}
                      onChange={(event) => setEmployeeQuestion(event.target.value)}
                      rows={3}
                      placeholder="Ask a question from available documents"
                      className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                    />
                    <button
                      type="submit"
                      disabled={isEmployeeBusy || !hasDocuments}
                      className="w-fit rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                    >
                      {employeeBusyState === "querying" ? "Querying..." : "Ask"}
                    </button>
                  </form>

                  {employeeQueryResult && (
                    <div className="mt-4 space-y-4">
                      <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-800 whitespace-pre-wrap">{employeeQueryResult.answer}</div>
                      <div>
                        <h3 className="text-sm font-medium text-slate-900">Source</h3>
                        {employeeQueryResult.sources.length === 0 ? (
                          <p className="mt-2 text-sm text-slate-600">No source available.</p>
                        ) : (
                          <div className="mt-2 rounded-md border border-slate-200 p-3">
                            <p className="text-sm font-medium text-slate-900">{employeeQueryResult.sources[0].title}</p>
                            <p className="mt-1 text-xs text-slate-600">
                              URL:{" "}
                              {employeeQueryResult.sources[0].source_url ? (
                                <a
                                  href={employeeQueryResult.sources[0].source_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-blue-700 underline"
                                >
                                  {employeeQueryResult.sources[0].source_url}
                                </a>
                              ) : (
                                "Not provided"
                              )}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </section>
              </>
            )}
          </section>
        ) : (
          <section className="grid gap-6 md:grid-cols-2">
          <form onSubmit={(event) => void handleUpload(event)} className="rounded-xl bg-white p-5 shadow-sm">
            <h2 className="text-lg font-medium text-slate-900">Upload PDF</h2>
            <div className="mt-4 space-y-3">
              <input
                type="file"
                accept="application/pdf"
                onChange={(event) => {
                  setSelectedFile(event.target.files?.[0] ?? null);
                  setStatusMessage(null);
                  setError(null);
                }}
                className="block w-full text-sm text-slate-700"
              />
              <input
                type="url"
                placeholder="Optional source URL"
                value={sourceUrl}
                onChange={(event) => setSourceUrl(event.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <button
              type="submit"
              disabled={isBusy}
              className="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {busyState === "uploading" ? "Uploading..." : "Upload / Import"}
            </button>
          </form>

          <div className="rounded-xl bg-white p-5 shadow-sm">
            <h2 className="text-lg font-medium text-slate-900">Indexed Documents</h2>
            {!hasDocuments ? (
              <p className="mt-3 text-sm text-slate-600">No documents uploaded yet.</p>
            ) : (
              <ul className="mt-3 space-y-3">
                {documents.map((doc) => (
                  <li key={doc.id} className="rounded-md border border-slate-200 p-3">
                    <p className="font-medium text-slate-900">{doc.title}</p>
                    <p className="mt-1 text-xs text-slate-600">Added: {new Date(doc.created_at).toLocaleString()}</p>
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => void handleDelete(doc.id)}
                      className="mt-2 rounded-md border border-slate-300 px-3 py-1 text-xs text-slate-700 disabled:opacity-50"
                    >
                      {busyState === "deleting" ? "Deleting..." : "Delete"}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          </section>
        )}

        {portal === "admin" && (
        <section className="rounded-xl bg-white p-5 shadow-sm">
          <h2 className="text-lg font-medium text-slate-900">Query Test</h2>
          <form onSubmit={(event) => void handleQuery(event)} className="mt-3 flex flex-col gap-3">
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              rows={3}
              placeholder="Ask a question about uploaded documents"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            <button
              type="submit"
              disabled={isBusy || !hasDocuments}
              className="w-fit rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {busyState === "querying" ? "Querying..." : "Run Query"}
            </button>
          </form>

          {queryResult && (
            <div className="mt-4 space-y-4">
              <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-800 whitespace-pre-wrap">{queryResult.answer}</div>
              <div>
                <h3 className="text-sm font-medium text-slate-900">Sources</h3>
                {queryResult.sources.length === 0 ? (
                  <p className="mt-2 text-sm text-slate-600">No matching sources found.</p>
                ) : (
                  <ul className="mt-2 space-y-2">
                    {queryResult.sources.map((source, index) => (
                      <li key={`${source.document_id}-${source.chunk_index}-${index}`} className="rounded-md border border-slate-200 p-3">
                        <p className="text-sm font-medium text-slate-900">{source.title}</p>
                        <p className="mt-1 text-xs text-slate-600">
                          URL:{" "}
                          {source.source_url ? (
                            <a
                              href={source.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-blue-700 underline"
                            >
                              {source.source_url}
                            </a>
                          ) : (
                            "Not provided"
                          )}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </section>
        )}
      </div>
    </main>
  );
}

export default App;
