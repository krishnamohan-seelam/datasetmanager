import apiClient from './axios';
import {
    Dataset,
    DatasetFilters,
    DatasetUploadData,
    DatasetRow,
    DatasetPermission,
    DatasetColumn,
    Batch,
    SchemaVersion,
} from '../types/dataset.types';
import { PaginatedResponse, PaginationParams } from '../types/common.types';

export const datasetsApi = {
    // List datasets with pagination and filters
    listDatasets: async (
        params: PaginationParams & DatasetFilters
    ): Promise<PaginatedResponse<Dataset>> => {
        const response = await apiClient.get<PaginatedResponse<Dataset>>('/datasets', { params });
        return response.data;
    },

    // Get single dataset by ID
    getDataset: async (datasetId: string): Promise<Dataset> => {
        const response = await apiClient.get<Dataset>(`/datasets/${datasetId}`);
        return response.data;
    },

    // Upload new dataset
    uploadDataset: async (data: DatasetUploadData): Promise<{ id: string; name: string; row_count: number; status: string; batch_frequency: string }> => {
        const formData = new FormData();
        formData.append('file', data.file);
        formData.append('name', data.name);
        if (data.description) formData.append('description', data.description);
        if (data.tags) formData.append('tags', data.tags.join(','));
        if (data.is_public !== undefined) formData.append('is_public', String(data.is_public));
        if (data.masking_config) {
            formData.append('masking_config', JSON.stringify(data.masking_config));
        }
        if (data.batch_frequency) formData.append('batch_frequency', data.batch_frequency);
        if (data.batch_date) formData.append('batch_date', data.batch_date);

        const response = await apiClient.post(
            '/datasets',
            formData,
            {
                headers: { 'Content-Type': 'multipart/form-data' },
            }
        );
        return response.data;
    },

    // Update dataset metadata
    updateDataset: async (
        datasetId: string,
        updates: Partial<Dataset>
    ): Promise<{ id: string; message: string }> => {
        const response = await apiClient.patch<{ id: string; message: string }>(
            `/datasets/${datasetId}/meta`,
            updates
        );
        return response.data;
    },

    // Delete dataset
    deleteDataset: async (datasetId: string): Promise<{ id: string; message: string }> => {
        const response = await apiClient.delete<{ id: string; message: string }>(
            `/datasets/${datasetId}`,
            { params: { confirm: true } }
        );
        return response.data;
    },

    // Get dataset rows with pagination (supports batch filtering)
    getDatasetRows: async (
        datasetId: string,
        params: PaginationParams & { columns?: string; batch_id?: string }
    ): Promise<PaginatedResponse<DatasetRow>> => {
        const response = await apiClient.get<PaginatedResponse<DatasetRow>>(
            `/datasets/${datasetId}/rows`,
            { params }
        );
        return response.data;
    },

    // Download dataset
    downloadDataset: async (
        datasetId: string,
        format: 'csv' | 'json' | 'parquet' = 'csv'
    ): Promise<Blob> => {
        const response = await apiClient.get(`/datasets/${datasetId}/download`, {
            params: { format },
            responseType: 'blob',
        });
        return response.data;
    },

    // ── Permissions ─────────────────────────────────────────────────

    grantPermission: async (
        datasetId: string,
        userEmail: string,
        role: string
    ): Promise<{ message: string }> => {
        const response = await apiClient.post<{ message: string }>(
            `/datasets/${datasetId}/permissions`,
            null,
            { params: { user_email: userEmail, role } }
        );
        return response.data;
    },

    revokePermission: async (
        datasetId: string,
        userEmail: string
    ): Promise<{ message: string }> => {
        const response = await apiClient.delete<{ message: string }>(
            `/datasets/${datasetId}/permissions/${userEmail}`
        );
        return response.data;
    },

    fetchPermissions: async (datasetId: string): Promise<DatasetPermission[]> => {
        const response = await apiClient.get<DatasetPermission[]>(`/datasets/${datasetId}/permissions`);
        return response.data;
    },

    // ── Schema ──────────────────────────────────────────────────────

    fetchSchema: async (datasetId: string, version?: number): Promise<DatasetColumn[]> => {
        const params = version !== undefined ? { version } : {};
        const response = await apiClient.get<DatasetColumn[]>(
            `/datasets/${datasetId}/schema`,
            { params }
        );
        return response.data;
    },

    fetchSchemaHistory: async (datasetId: string): Promise<SchemaVersion[]> => {
        const response = await apiClient.get<SchemaVersion[]>(
            `/datasets/${datasetId}/schema/history`
        );
        return response.data;
    },

    updateMaskingRule: async (
        datasetId: string,
        columnName: string,
        maskRule: string | null
    ): Promise<{ message: string }> => {
        const response = await apiClient.patch<{ message: string }>(
            `/datasets/${datasetId}/schema/${columnName}/masking`,
            null,
            { params: { mask_rule: maskRule } }
        );
        return response.data;
    },

    // ── Batches ─────────────────────────────────────────────────────

    listBatches: async (
        datasetId: string,
        params: PaginationParams
    ): Promise<PaginatedResponse<Batch>> => {
        const response = await apiClient.get<PaginatedResponse<Batch>>(
            `/datasets/${datasetId}/batches`,
            { params }
        );
        return response.data;
    },

    deleteBatch: async (
        datasetId: string,
        batchId: string
    ): Promise<{ message: string; batch_id: string }> => {
        const response = await apiClient.delete<{ message: string; batch_id: string }>(
            `/datasets/${datasetId}/batches/${batchId}`
        );
        return response.data;
    },
};
