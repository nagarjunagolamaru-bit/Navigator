export interface DocumentMetadata {
	id: string;
	title: string;
	source_url: string | null;
	created_at: string;
}

export interface DocumentUploadResponse {
	document: DocumentMetadata;
	chunk_count: number;
}

export interface DocumentListResponse {
	documents: DocumentMetadata[];
}

export interface QueryRequest {
	question: string;
	top_k?: number;
}

export interface QuerySource {
	document_id: string;
	title: string;
	source_url: string | null;
	chunk_index: number;
	excerpt: string;
	score: number;
}

export interface QueryResponse {
	answer: string;
	sources: QuerySource[];
}

export interface UserProfile {
	id: string;
	username: string;
	email: string;
	is_admin: boolean;
	created_at: string;
}

export interface LoginRequest {
	identifier: string;
	password: string;
}

export interface RegisterRequest {
	username: string;
	email: string;
	password: string;
}

export interface AuthResponse {
	token: string;
	user: UserProfile;
}
