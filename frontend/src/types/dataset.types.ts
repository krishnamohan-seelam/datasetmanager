// Dataset types

export type BatchFrequency = 'once' | 'hourly' | 'daily' | 'weekly' | 'monthly';

export interface Dataset {
    id: string;
    name: string;
    description: string;
    owner: string;
    created_at: string;
    updated_at: string;
    row_count: number;
    size_bytes: number;
    file_format: 'csv' | 'json' | 'parquet';
    status: 'uploading' | 'processing' | 'ready' | 'failed';
    storage_path?: string;
    version: number;
    tags: string[];
    is_public: boolean;
    schema?: DatasetColumn[];
    statistics?: DatasetStatistics;
    permissions?: DatasetPermissions;
    // Batch & schema tracking
    batch_frequency: BatchFrequency;
    latest_batch_date?: string;
    total_batches: number;
    schema_version: number;
}

export interface DatasetColumn {
    name: string;
    type: string;
    nullable: boolean;
    masked: boolean;
    mask_rule?: string;
    position: number;
    is_active: boolean;
}

export interface DatasetStatistics {
    total_rows: number;
    total_columns: number;
    null_count: number;
    duplicate_rows: number;
}

export interface DatasetPermission {
    user_email: string;
    role: 'admin' | 'contributor' | 'viewer';
    granted_at?: string;
}

export interface DatasetPermissions {
    admins: string[];
    contributors: string[];
    viewers: string[];
}

export interface DatasetFilters {
    search?: string;
    owner?: string;
    tags?: string;
    is_public?: boolean;
    status?: string;
    sort_by?: 'created_at' | 'updated_at' | 'name' | 'row_count';
    order?: 'asc' | 'desc';
}

export interface DatasetUploadData {
    file: File;
    name: string;
    description?: string;
    tags?: string[];
    is_public?: boolean;
    masking_config?: Record<string, string>;
    batch_frequency?: BatchFrequency;
    batch_date?: string;
}

export interface DatasetRow {
    [key: string]: any;
}

// Batch types

export interface Batch {
    batch_id: string;
    batch_date: string;
    schema_version: number;
    row_count: number;
    size_bytes: number;
    file_format: string;
    status: string;
    uploaded_by: string;
    created_at: string;
}

// Schema version types

export interface SchemaVersion {
    version: number;
    batch_id?: string;
    created_at?: string;
    column_count: number;
    change_summary?: string;
    columns?: DatasetColumn[];
}
