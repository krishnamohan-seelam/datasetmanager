// User and authentication types

export interface User {
    email: string;
    role: 'admin' | 'contributor' | 'viewer';
    created_at: string;
}

export interface LoginCredentials {
    email: string;
    password: string;
}

export interface RegisterData {
    email: string;
    password: string;
    role?: 'contributor' | 'viewer';
}

export interface AuthResponse {
    user: User;
    token: string;
    message?: string;
}
