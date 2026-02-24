import apiClient from './axios';

export interface AdminStats {
    total_users: number;
    total_datasets: number;
    total_storage_bytes: number;
    system_status: string;
    timestamp: string;
}

export interface AdminUser {
    email: string;
    role: string;
    created_at: string | null;
}

export interface AdminUsersResponse {
    total: number;
    page: number;
    page_size: number;
    pages: number;
    items: AdminUser[];
}

export const adminApi = {
    getStats: async (): Promise<AdminStats> => {
        const response = await apiClient.get<AdminStats>('/admin/stats');
        return response.data;
    },

    getUsers: async (page = 1, pageSize = 50): Promise<AdminUsersResponse> => {
        const response = await apiClient.get<AdminUsersResponse>('/admin/users', {
            params: { page, page_size: pageSize },
        });
        return response.data;
    },

    clearCache: async (): Promise<{ message: string }> => {
        const response = await apiClient.post<{ message: string }>('/admin/cache/clear');
        return response.data;
    },
};
