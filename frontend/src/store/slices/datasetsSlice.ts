import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { datasetsApi } from '../../api/datasets.api';
import {
    Dataset,
    DatasetFilters,
    DatasetUploadData,
    DatasetRow,
    DatasetPermission,
    DatasetColumn,
} from '../../types/dataset.types';
import { PaginatedResponse, PaginationParams } from '../../types/common.types';

interface DatasetsState {
    items: Dataset[];
    currentDataset: Dataset | null;
    currentDatasetRows: DatasetRow[];
    currentDatasetPermissions: DatasetPermission[];
    currentDatasetSchema: DatasetColumn[];
    filters: DatasetFilters;
    pagination: {
        page: number;
        page_size: number;
        total: number;
        pages: number;
    };
    rowsPagination: {
        page: number;
        page_size: number;
        total: number;
        pages: number;
    };
    loading: boolean;
    uploading: boolean;
    error: string | null;
}

const initialState: DatasetsState = {
    items: [],
    currentDataset: null,
    currentDatasetRows: [],
    currentDatasetPermissions: [],
    currentDatasetSchema: [],
    filters: {
        sort_by: 'created_at',
        order: 'desc',
    },
    pagination: {
        page: 1,
        page_size: 20,
        total: 0,
        pages: 0,
    },
    rowsPagination: {
        page: 1,
        page_size: 100,
        total: 0,
        pages: 0,
    },
    loading: false,
    uploading: false,
    error: null,
};

// Async thunks
export const fetchDatasets = createAsyncThunk(
    'datasets/fetchDatasets',
    async (params: PaginationParams & DatasetFilters, { rejectWithValue }) => {
        try {
            const response = await datasetsApi.listDatasets(params);
            return response;
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.error?.message || 'Failed to fetch datasets');
        }
    }
);

export const fetchDataset = createAsyncThunk(
    'datasets/fetchDataset',
    async (datasetId: string, { rejectWithValue }) => {
        try {
            const dataset = await datasetsApi.getDataset(datasetId);
            return dataset;
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.error?.message || 'Failed to fetch dataset');
        }
    }
);

export const uploadDataset = createAsyncThunk(
    'datasets/uploadDataset',
    async (data: DatasetUploadData, { rejectWithValue }) => {
        try {
            const response = await datasetsApi.uploadDataset(data);
            return response;
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.error?.message || 'Failed to upload dataset');
        }
    }
);

export const downloadDataset = createAsyncThunk(
    'datasets/downloadDataset',
    async ({ id, format }: { id: string; format: 'csv' | 'json' | 'parquet' }, { rejectWithValue }) => {
        try {
            const blob = await datasetsApi.downloadDataset(id, format);
            return { blob, format };
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.error?.message || 'Failed to download dataset');
        }
    }
);

export const grantPermission = createAsyncThunk(
    'datasets/grantPermission',
    async (
        { datasetId, userEmail, role }: { datasetId: string; userEmail: string; role: string },
        { rejectWithValue }
    ) => {
        try {
            await datasetsApi.grantPermission(datasetId, userEmail, role);
            return { datasetId, userEmail, role };
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.error?.message || 'Failed to grant permission');
        }
    }
);

export const revokePermission = createAsyncThunk(
    'datasets/revokePermission',
    async (
        { datasetId, userEmail }: { datasetId: string; userEmail: string },
        { rejectWithValue }
    ) => {
        try {
            await datasetsApi.revokePermission(datasetId, userEmail);
            return { datasetId, userEmail };
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.error?.message || 'Failed to revoke permission');
        }
    }
);

export const updateDataset = createAsyncThunk(
    'datasets/updateDataset',
    async ({ id, updates }: { id: string; updates: Partial<Dataset> }, { rejectWithValue }) => {
        try {
            const response = await datasetsApi.updateDataset(id, updates);
            return { id, updates };
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.error?.message || 'Failed to update dataset');
        }
    }
);

export const deleteDataset = createAsyncThunk(
    'datasets/deleteDataset',
    async (datasetId: string, { rejectWithValue }) => {
        try {
            await datasetsApi.deleteDataset(datasetId);
            return datasetId;
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.error?.message || 'Failed to delete dataset');
        }
    }
);

export const fetchDatasetRows = createAsyncThunk(
    'datasets/fetchDatasetRows',
    async (
        { datasetId, params }: { datasetId: string; params: PaginationParams },
        { rejectWithValue }
    ) => {
        try {
            const response = await datasetsApi.getDatasetRows(datasetId, params);
            return response;
        } catch (error: any) {
            return rejectWithValue(
                error.response?.data?.error?.message || 'Failed to fetch dataset rows'
            );
        }
    }
);

export const fetchPermissions = createAsyncThunk(
    'datasets/fetchPermissions',
    async (datasetId: string, { rejectWithValue }) => {
        try {
            const permissions = await datasetsApi.fetchPermissions(datasetId);
            return permissions;
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.error?.message || 'Failed to fetch permissions');
        }
    }
);

export const fetchSchema = createAsyncThunk(
    'datasets/fetchSchema',
    async (datasetId: string, { rejectWithValue }) => {
        try {
            const schema = await datasetsApi.fetchSchema(datasetId);
            return schema;
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.error?.message || 'Failed to fetch schema');
        }
    }
);

export const updateMaskingRule = createAsyncThunk(
    'datasets/updateMaskingRule',
    async (
        { datasetId, columnName, maskRule }: { datasetId: string; columnName: string; maskRule: string | null },
        { rejectWithValue }
    ) => {
        try {
            await datasetsApi.updateMaskingRule(datasetId, columnName, maskRule);
            return { datasetId, columnName, maskRule };
        } catch (error: any) {
            return rejectWithValue(error.response?.data?.error?.message || 'Failed to update masking rule');
        }
    }
);

const datasetsSlice = createSlice({
    name: 'datasets',
    initialState,
    reducers: {
        setFilters: (state, action: PayloadAction<DatasetFilters>) => {
            state.filters = { ...state.filters, ...action.payload };
        },
        setPagination: (state, action: PayloadAction<Partial<typeof initialState.pagination>>) => {
            state.pagination = { ...state.pagination, ...action.payload };
        },
        setRowsPagination: (
            state,
            action: PayloadAction<Partial<typeof initialState.rowsPagination>>
        ) => {
            state.rowsPagination = { ...state.rowsPagination, ...action.payload };
        },
        clearCurrentDataset: (state) => {
            state.currentDataset = null;
            state.currentDatasetRows = [];
        },
        clearError: (state) => {
            state.error = null;
        },
    },
    extraReducers: (builder) => {
        // Fetch datasets
        builder
            .addCase(fetchDatasets.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(
                fetchDatasets.fulfilled,
                (state, action: PayloadAction<PaginatedResponse<Dataset>>) => {
                    state.loading = false;
                    state.items = action.payload.items;
                    state.pagination = {
                        page: action.payload.page,
                        page_size: action.payload.page_size,
                        total: action.payload.total,
                        pages: action.payload.pages,
                    };
                }
            )
            .addCase(fetchDatasets.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload as string;
            });

        // Fetch single dataset
        builder
            .addCase(fetchDataset.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchDataset.fulfilled, (state, action: PayloadAction<Dataset>) => {
                state.loading = false;
                state.currentDataset = action.payload;
            })
            .addCase(fetchDataset.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload as string;
            });

        // Upload dataset
        builder
            .addCase(uploadDataset.pending, (state) => {
                state.uploading = true;
                state.error = null;
            })
            .addCase(uploadDataset.fulfilled, (state) => {
                state.uploading = false;
            })
            .addCase(uploadDataset.rejected, (state, action) => {
                state.uploading = false;
                state.error = action.payload as string;
            });

        // Update dataset
        builder
            .addCase(updateDataset.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(
                updateDataset.fulfilled,
                (state, action: PayloadAction<{ id: string; updates: Partial<Dataset> }>) => {
                    state.loading = false;
                    if (state.currentDataset && state.currentDataset.id === action.payload.id) {
                        state.currentDataset = { ...state.currentDataset, ...action.payload.updates };
                    }
                }
            )
            .addCase(updateDataset.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload as string;
            });

        // Delete dataset
        builder
            .addCase(deleteDataset.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(deleteDataset.fulfilled, (state, action: PayloadAction<string>) => {
                state.loading = false;
                state.items = state.items.filter((dataset) => dataset.id !== action.payload);
                if (state.currentDataset?.id === action.payload) {
                    state.currentDataset = null;
                }
            })
            .addCase(deleteDataset.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload as string;
            });

        // Fetch dataset rows
        builder
            .addCase(fetchDatasetRows.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(
                fetchDatasetRows.fulfilled,
                (state, action: PayloadAction<PaginatedResponse<DatasetRow>>) => {
                    state.loading = false;
                    state.currentDatasetRows = action.payload.items;
                    state.rowsPagination = {
                        page: action.payload.page,
                        page_size: action.payload.page_size,
                        total: action.payload.total,
                        pages: action.payload.pages,
                    };
                }
            )
            .addCase(fetchDatasetRows.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload as string;
            });

        // Fetch permissions
        builder
            .addCase(fetchPermissions.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchPermissions.fulfilled, (state, action: PayloadAction<DatasetPermission[]>) => {
                state.loading = false;
                state.currentDatasetPermissions = action.payload;
            })
            .addCase(fetchPermissions.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload as string;
            });

        // Grant permission
        builder
            .addCase(grantPermission.fulfilled, (state, action) => {
                const { userEmail, role } = action.payload;
                const existing = state.currentDatasetPermissions.find(p => p.user_email === userEmail);
                if (existing) {
                    existing.role = role as any;
                } else {
                    state.currentDatasetPermissions.push({
                        user_email: userEmail,
                        role: role as any,
                        granted_at: new Date().toISOString()
                    });
                }
            });

        // Revoke permission
        builder
            .addCase(revokePermission.fulfilled, (state, action) => {
                state.currentDatasetPermissions = state.currentDatasetPermissions.filter(
                    p => p.user_email !== action.payload.userEmail
                );
            });

        // Fetch schema
        builder
            .addCase(fetchSchema.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchSchema.fulfilled, (state, action: PayloadAction<DatasetColumn[]>) => {
                state.loading = false;
                state.currentDatasetSchema = action.payload;
            })
            .addCase(fetchSchema.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload as string;
            });

        // Update masking rule
        builder
            .addCase(updateMaskingRule.fulfilled, (state, action) => {
                const { columnName, maskRule } = action.payload;
                const col = state.currentDatasetSchema.find(c => c.name === columnName);
                if (col) {
                    col.mask_rule = maskRule || undefined;
                    col.masked = !!maskRule;
                }
            });
    },
});

export const { setFilters, setPagination, setRowsPagination, clearCurrentDataset, clearError } =
    datasetsSlice.actions;
export default datasetsSlice.reducer;
