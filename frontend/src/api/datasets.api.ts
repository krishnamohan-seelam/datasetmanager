import apiClient from './axios';
import {
    Dataset,
    DatasetFilters,
    DatasetUploadData,
    DatasetRow,
    DatasetPermission,
    DatasetColumn,
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
    uploadDataset: async (data: DatasetUploadData): Promise<{ id: string; message: string }> => {
        const formData = new FormData();
        formData.append('file', data.file);
        formData.append('name', data.name);
        if (data.description) formData.append('description', data.description);
        if (data.tags) formData.append('tags', data.tags.join(','));
        if (data.is_public !== undefined) formData.append('is_public', String(data.is_public));
        if (data.masking_config) {
            formData.append('masking_config', JSON.stringify(data.masking_config));
        }

        const response = await apiClient.post<{ id: string; message: string }>(
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

    // Get dataset rows with pagination
    getDatasetRows: async (
        datasetId: string,
        params: PaginationParams & { columns?: string }
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

    // Grant permission
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

    // Revoke permission
    revokePermission: async (
        datasetId: string,
        userEmail: string
    ): Promise<{ message: string }> => {
        const response = await apiClient.delete<{ message: string }>(
            `/datasets/${datasetId}/permissions/${userEmail}`
        );
        return response.data;
    },

    // List permissions
    fetchPermissions: async (datasetId: string): Promise<DatasetPermission[]> => {
        const response = await apiClient.get<DatasetPermission[]>(`/datasets/${datasetId}/permissions`);
        return response.data;
    },

    // Get schema
    fetchSchema: async (datasetId: string): Promise<DatasetColumn[]> => {
        const response = await apiClient.get<DatasetColumn[]>(`/datasets/${datasetId}/schema`);
        return response.data;
    },

    // Update masking rule
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
};
