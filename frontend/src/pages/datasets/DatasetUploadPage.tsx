import React, { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm, Controller, SubmitHandler } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useDropzone } from 'react-dropzone';
import {
    Container,
    Paper,
    Typography,
    TextField,
    Button,
    Box,
    FormControlLabel,
    Switch,
    Chip,
    Stack,
    FormHelperText,
    CircularProgress,
    IconButton,
    Breadcrumbs,
    Link,
    Divider,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
} from '@mui/material';
import {
    CloudUpload as CloudUploadIcon,
    Close as CloseIcon,
    InsertDriveFile as FileIcon,
    ArrowBack as ArrowBackIcon,
} from '@mui/icons-material';
import { useAppDispatch, useAppSelector } from '../../store/hooks';
import { uploadDataset } from '../../store/slices/datasetsSlice';
import { useSnackbar } from 'notistack';
import { BatchFrequency } from '../../types/dataset.types';

const schema = z.object({
    name: z.string().min(3, 'Name must be at least 3 characters'),
    description: z.string().optional().default(''),
    tags: z.array(z.string()).default([]),
    is_public: z.boolean().default(false),
    batch_frequency: z.string().default('once'),
    batch_date: z.string().optional().default(''),
});

type FormData = z.infer<typeof schema>;

const BATCH_FREQUENCY_OPTIONS: { value: BatchFrequency; label: string; description: string }[] = [
    { value: 'once', label: 'One-time', description: 'Single upload, no recurring batches' },
    { value: 'hourly', label: 'Hourly', description: 'Data arrives every hour' },
    { value: 'daily', label: 'Daily', description: 'Data arrives once per day' },
    { value: 'weekly', label: 'Weekly', description: 'Data arrives once per week' },
    { value: 'monthly', label: 'Monthly', description: 'Data arrives once per month' },
];

const DatasetUploadPage: React.FC = () => {
    const navigate = useNavigate();
    const dispatch = useAppDispatch();
    const { enqueueSnackbar } = useSnackbar();
    const { uploading } = useAppSelector((state) => state.datasets);

    const [file, setFile] = useState<File | null>(null);
    const [tagInput, setTagInput] = useState('');

    const {
        control,
        handleSubmit,
        setValue,
        watch,
        formState: { errors },
    } = useForm({
        resolver: zodResolver(schema),
        defaultValues: {
            name: '',
            description: '',
            tags: [],
            is_public: false,
            batch_frequency: 'once',
            batch_date: '',
        },
    });

    const tags = watch('tags');
    const batchFrequency = watch('batch_frequency');

    const onDrop = useCallback((acceptedFiles: File[]) => {
        if (acceptedFiles.length > 0) {
            setFile(acceptedFiles[0]);
            const currentName = watch('name');
            if (!currentName) {
                const fileName = acceptedFiles[0].name.split('.').slice(0, -1).join('.');
                setValue('name', fileName);
            }
        }
    }, [setValue, watch]);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        multiple: false,
        accept: {
            'text/csv': ['.csv'],
            'application/json': ['.json'],
            'application/vnd.apache.parquet': ['.parquet'],
        },
    });

    const removeFile = () => {
        setFile(null);
    };

    const handleAddTag = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && tagInput.trim()) {
            e.preventDefault();
            if (!tags.includes(tagInput.trim())) {
                setValue('tags', [...tags, tagInput.trim()]);
            }
            setTagInput('');
        }
    };

    const handleRemoveTag = (tagToRemove: string) => {
        setValue('tags', tags.filter(tag => tag !== tagToRemove));
    };

    const onSubmit: SubmitHandler<FormData> = async (data) => {
        if (!file) {
            enqueueSnackbar('Please select a file to upload', { variant: 'error' });
            return;
        }

        try {
            const result = await dispatch(uploadDataset({
                ...data,
                tags: data.tags || [],
                file,
                batch_frequency: data.batch_frequency as BatchFrequency,
                batch_date: data.batch_date || undefined,
            })).unwrap();

            enqueueSnackbar('Dataset uploaded successfully!', { variant: 'success' });
            navigate(`/datasets/${result.id}`);
        } catch (error: any) {
            enqueueSnackbar(error || 'Failed to upload dataset', { variant: 'error' });
        }
    };

    return (
        <Container maxWidth="md" sx={{ py: 4 }}>
            <Box sx={{ mb: 4 }}>
                <Breadcrumbs aria-label="breadcrumb" sx={{ mb: 2 }}>
                    <Link underline="hover" color="inherit" onClick={() => navigate('/datasets')} sx={{ cursor: 'pointer' }}>
                        Datasets
                    </Link>
                    <Typography color="text.primary">Upload</Typography>
                </Breadcrumbs>
                <Typography variant="h4" component="h1" gutterBottom fontWeight="bold">
                    Upload Dataset
                </Typography>
                <Typography variant="body1" color="text.secondary">
                    Upload your CSV, JSON, or Parquet files to start managing and analyzing your data.
                </Typography>
            </Box>

            <Paper sx={{ p: { xs: 3, md: 4 }, borderRadius: 3 }}>
                <form onSubmit={handleSubmit(onSubmit)}>
                    {/* Step 1: File */}
                    <Box sx={{ mb: 4 }}>
                        <Typography variant="h6" gutterBottom>
                            1. Select File
                        </Typography>
                        {!file ? (
                            <Box
                                {...getRootProps()}
                                sx={{
                                    border: '2px dashed',
                                    borderColor: isDragActive ? 'primary.main' : 'divider',
                                    borderRadius: 2,
                                    p: 6,
                                    textAlign: 'center',
                                    cursor: 'pointer',
                                    bgcolor: isDragActive ? 'action.hover' : 'background.paper',
                                    transition: 'all 0.2s ease',
                                    '&:hover': {
                                        borderColor: 'primary.main',
                                        bgcolor: 'action.hover',
                                    },
                                }}
                            >
                                <input {...getInputProps()} />
                                <CloudUploadIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                                <Typography variant="h6">
                                    {isDragActive ? 'Drop the file here' : 'Drag & drop a file here'}
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                    or click to select a file from your computer
                                </Typography>
                                <Typography variant="caption" display="block" sx={{ mt: 1 }}>
                                    Supported formats: .csv, .json, .parquet (Max: 10GB)
                                </Typography>
                            </Box>
                        ) : (
                            <Paper
                                variant="outlined"
                                sx={{
                                    p: 2,
                                    display: 'flex',
                                    alignItems: 'center',
                                    borderColor: 'primary.main',
                                    bgcolor: 'primary.50',
                                }}
                            >
                                <FileIcon sx={{ mr: 2, color: 'primary.main', fontSize: 32 }} />
                                <Box sx={{ flexGrow: 1 }}>
                                    <Typography variant="subtitle1" fontWeight="bold">
                                        {file.name}
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        {(file.size / (1024 * 1024)).toFixed(2)} MB
                                    </Typography>
                                </Box>
                                <IconButton onClick={removeFile} disabled={uploading}>
                                    <CloseIcon />
                                </IconButton>
                            </Paper>
                        )}
                    </Box>

                    <Divider sx={{ my: 4 }} />

                    {/* Step 2: Details */}
                    <Box sx={{ mb: 4 }}>
                        <Typography variant="h6" gutterBottom>
                            2. Dataset Details
                        </Typography>
                        <Stack spacing={3}>
                            <Controller
                                name="name"
                                control={control}
                                render={({ field }) => (
                                    <TextField
                                        {...field}
                                        label="Dataset Name"
                                        fullWidth
                                        error={!!errors.name}
                                        helperText={errors.name?.message}
                                        disabled={uploading}
                                    />
                                )}
                            />

                            <Controller
                                name="description"
                                control={control}
                                render={({ field }) => (
                                    <TextField
                                        {...field}
                                        label="Description"
                                        fullWidth
                                        multiline
                                        rows={4}
                                        placeholder="Briefly describe what this dataset contains..."
                                        disabled={uploading}
                                    />
                                )}
                            />

                            <Box>
                                <TextField
                                    label="Add Tags"
                                    fullWidth
                                    value={tagInput}
                                    onChange={(e) => setTagInput(e.target.value)}
                                    onKeyDown={handleAddTag}
                                    placeholder="Type and press Enter to add tags"
                                    disabled={uploading}
                                    helperText="Tags help you organize and find your datasets later"
                                />
                                <Stack direction="row" spacing={1} sx={{ mt: 1, flexWrap: 'wrap', gap: 1 }}>
                                    {tags.map((tag) => (
                                        <Chip
                                            key={tag}
                                            label={tag}
                                            onDelete={() => handleRemoveTag(tag)}
                                            size="small"
                                            color="primary"
                                            variant="outlined"
                                            disabled={uploading}
                                        />
                                    ))}
                                </Stack>
                            </Box>

                            <Controller
                                name="is_public"
                                control={control}
                                render={({ field }) => (
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                {...field}
                                                checked={field.value}
                                                onChange={(e) => field.onChange(e.target.checked)}
                                                disabled={uploading}
                                            />
                                        }
                                        label={
                                            <Box>
                                                <Typography variant="subtitle2">Public Dataset</Typography>
                                                <Typography variant="caption" color="text.secondary">
                                                    If enabled, other users will be able to discover and read this dataset.
                                                </Typography>
                                            </Box>
                                        }
                                    />
                                )}
                            />
                        </Stack>
                    </Box>

                    <Divider sx={{ my: 4 }} />

                    {/* Step 3: Ingestion Schedule */}
                    <Box sx={{ mb: 4 }}>
                        <Typography variant="h6" gutterBottom>
                            3. Ingestion Schedule
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                            Configure how often new data batches will be uploaded to this dataset.
                        </Typography>
                        <Stack spacing={3}>
                            <Controller
                                name="batch_frequency"
                                control={control}
                                render={({ field }) => (
                                    <FormControl fullWidth disabled={uploading}>
                                        <InputLabel>Batch Frequency</InputLabel>
                                        <Select {...field} label="Batch Frequency">
                                            {BATCH_FREQUENCY_OPTIONS.map((opt) => (
                                                <MenuItem key={opt.value} value={opt.value}>
                                                    <Box>
                                                        <Typography variant="body2" fontWeight="medium">
                                                            {opt.label}
                                                        </Typography>
                                                        <Typography variant="caption" color="text.secondary">
                                                            {opt.description}
                                                        </Typography>
                                                    </Box>
                                                </MenuItem>
                                            ))}
                                        </Select>
                                        <FormHelperText>
                                            Choose how frequently you'll append new data to this dataset
                                        </FormHelperText>
                                    </FormControl>
                                )}
                            />

                            {batchFrequency !== 'once' && (
                                <Controller
                                    name="batch_date"
                                    control={control}
                                    render={({ field }) => (
                                        <TextField
                                            {...field}
                                            label="Batch Date (optional)"
                                            type="datetime-local"
                                            fullWidth
                                            disabled={uploading}
                                            InputLabelProps={{ shrink: true }}
                                            helperText="Date this batch represents. Defaults to now if not set."
                                        />
                                    )}
                                />
                            )}
                        </Stack>
                    </Box>

                    <Box sx={{ mt: 6, display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
                        <Button
                            variant="outlined"
                            onClick={() => navigate('/datasets')}
                            disabled={uploading}
                            size="large"
                        >
                            Cancel
                        </Button>
                        <Button
                            type="submit"
                            variant="contained"
                            disabled={uploading || !file}
                            startIcon={uploading ? <CircularProgress size={20} color="inherit" /> : <CloudUploadIcon />}
                            size="large"
                        >
                            {uploading ? 'Uploading...' : 'Upload Dataset'}
                        </Button>
                    </Box>
                </form>
            </Paper>
        </Container>
    );
};

export default DatasetUploadPage;
