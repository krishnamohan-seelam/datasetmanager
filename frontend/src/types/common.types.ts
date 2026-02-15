// Common types used across the application

export interface PaginationParams {
    page: number;
    page_size: number;
}

export interface PaginatedResponse<T> {
    total: number;
    page: number;
    page_size: number;
    pages: number;
    items: T[];
}

export interface ApiError {
    error: {
        code: string;
        message: string;
        details?: Record<string, any>;
    };
}
