import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { adminApi, AdminStats, AdminUser, AdminUsersResponse } from '../../api/admin.api';

interface AdminState {
    stats: AdminStats | null;
    users: AdminUser[];
    usersPagination: {
        page: number;
        page_size: number;
        total: number;
        pages: number;
    };
    loading: boolean;
    error: string | null;
}

const initialState: AdminState = {
    stats: null,
    users: [],
    usersPagination: {
        page: 1,
        page_size: 50,
        total: 0,
        pages: 0,
    },
    loading: false,
    error: null,
};

export const fetchAdminStats = createAsyncThunk(
    'admin/fetchStats',
    async (_, { rejectWithValue }) => {
        try {
            return await adminApi.getStats();
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.detail || 'Failed to fetch admin stats');
        }
    }
);

export const fetchUsers = createAsyncThunk(
    'admin/fetchUsers',
    async ({ page, pageSize }: { page?: number; pageSize?: number } = {}, { rejectWithValue }) => {
        try {
            return await adminApi.getUsers(page, pageSize);
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.detail || 'Failed to fetch users');
        }
    }
);

export const clearCache = createAsyncThunk(
    'admin/clearCache',
    async (_, { rejectWithValue }) => {
        try {
            return await adminApi.clearCache();
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.detail || 'Failed to clear cache');
        }
    }
);

const adminSlice = createSlice({
    name: 'admin',
    initialState,
    reducers: {
        clearAdminError: (state) => {
            state.error = null;
        },
    },
    extraReducers: (builder) => {
        // Fetch stats
        builder
            .addCase(fetchAdminStats.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchAdminStats.fulfilled, (state, action: PayloadAction<AdminStats>) => {
                state.loading = false;
                state.stats = action.payload;
            })
            .addCase(fetchAdminStats.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload as string;
            });

        // Fetch users
        builder
            .addCase(fetchUsers.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchUsers.fulfilled, (state, action: PayloadAction<AdminUsersResponse>) => {
                state.loading = false;
                state.users = action.payload.items;
                state.usersPagination = {
                    page: action.payload.page,
                    page_size: action.payload.page_size,
                    total: action.payload.total,
                    pages: action.payload.pages,
                };
            })
            .addCase(fetchUsers.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload as string;
            });

        // Clear cache
        builder
            .addCase(clearCache.pending, (state) => {
                state.loading = true;
            })
            .addCase(clearCache.fulfilled, (state) => {
                state.loading = false;
            })
            .addCase(clearCache.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload as string;
            });
    },
});

export const { clearAdminError } = adminSlice.actions;
export default adminSlice.reducer;
