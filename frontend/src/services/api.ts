import type {
  AuthResponse,
  DocumentListResponse,
  DocumentUploadResponse,
  LoginRequest,
  QueryRequest,
  QueryResponse,
  RegisterRequest,
  UserProfile,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let errorDetail = `API request failed with status ${response.status}`;
    try {
      const errorBody = await response.json() as { detail?: string | { [key: string]: unknown } };
      if (typeof errorBody.detail === "string") {
        errorDetail = errorBody.detail;
      }
    } catch {
      // If response is not JSON, use default error message
    }
    throw new Error(errorDetail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const responseText = await response.text();
  if (!responseText.trim()) {
    return undefined as T;
  }

  return JSON.parse(responseText) as T;
}

export async function uploadDocument(token: string, file?: File | null, sourceUrl?: string): Promise<DocumentUploadResponse> {
  const body = new FormData();
  if (file) {
    body.append("file", file);
  }
  if (sourceUrl?.trim()) {
    body.append("source_url", sourceUrl.trim());
  }

  if (!file && !sourceUrl?.trim()) {
    throw new Error("Choose a PDF file or provide a source URL.");
  }

  return apiRequest<DocumentUploadResponse>("/api/documents", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body,
  });
}

export async function listDocuments(token: string): Promise<DocumentListResponse> {
  return apiRequest<DocumentListResponse>("/api/documents", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

export async function deleteDocument(token: string, documentId: string): Promise<void> {
  await apiRequest<void>(`/api/documents/${documentId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

export async function queryKnowledgeBase(token: string, payload: QueryRequest): Promise<QueryResponse> {
  return apiRequest<QueryResponse>("/api/query", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
}

export async function registerEmployee(payload: RegisterRequest): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function loginEmployee(payload: LoginRequest): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getCurrentEmployee(token: string): Promise<UserProfile> {
  return apiRequest<UserProfile>("/api/auth/me", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

export async function logoutEmployee(token: string): Promise<void> {
  await apiRequest<void>("/api/auth/logout", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

export async function queryKnowledgeBaseForEmployee(token: string, payload: QueryRequest): Promise<QueryResponse> {
  return apiRequest<QueryResponse>("/api/employee/query", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
}
