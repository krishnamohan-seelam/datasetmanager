import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Box,
    Typography,
    TextField,
    Button,
    Grid,
    Card,
    CardContent,
    CardActions,
    Chip,
    InputAdornment,
    MenuItem,
    Select,
    FormControl,
    InputLabel,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { useAppDispatch, useAppSelector } from '../../store/hooks';
import { fetchDatasets, setFilters, setPagination } from '../../store/slices/datasetsSlice';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import { Dataset } from '../../types/dataset.types';

const DatasetListPage = () => {
    const navigate = useNavigate();
    const dispatch = useAppDispatch();
    const { items, filters, pagination, loading } = useAppSelector((state) => state.datasets);
    const [searchTerm, setSearchTerm] = useState('');

    useEffect(() => {
        dispatch(fetchDatasets({ ...pagination, ...filters }));
    }, [dispatch, pagination.page, pagination.page_size, filters]);

    const handleSearch = () => {
        dispatch(setFilters({ search: searchTerm }));
        dispatch(setPagination({ page: 1 }));
    };

    const handleSortChange = (sortBy: string) => {
        dispatch(setFilters({ sort_by: sortBy as any }));
    };

    const formatBytes = (bytes: number): string => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    };

    const formatDate = (dateString: string): string => {
        return new Date(dateString).toLocaleDateString();
    };

    if (loading && items.length === 0) {
        return <LoadingSpinner fullScreen />;
    }

    return (
        <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h4" component="h1">
                    Datasets
                </Typography>
                <Button variant="contained" onClick={() => navigate('/datasets/upload')}>
                    Upload Dataset
                </Button>
            </Box>

            <Box sx={{ mb: 3, display: 'flex', gap: 2 }}>
                <TextField
                    fullWidth
                    placeholder="Search datasets..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                    InputProps={{
                        startAdornment: (
                            <InputAdornment position="start">
                                <SearchIcon />
                            </InputAdornment>
                        ),
                    }}
                />
                <Button variant="outlined" onClick={handleSearch}>
                    Search
                </Button>
                <FormControl sx={{ minWidth: 200 }}>
                    <InputLabel>Sort By</InputLabel>
                    <Select
                        value={filters.sort_by || 'created_at'}
                        label="Sort By"
                        onChange={(e) => handleSortChange(e.target.value)}
                    >
                        <MenuItem value="created_at">Created Date</MenuItem>
                        <MenuItem value="updated_at">Updated Date</MenuItem>
                        <MenuItem value="name">Name</MenuItem>
                        <MenuItem value="row_count">Row Count</MenuItem>
                    </Select>
                </FormControl>
            </Box>

            {(items?.length || 0) === 0 ? (
                <Box sx={{ textAlign: 'center', py: 8 }}>
                    <Typography variant="h6" color="text.secondary">
                        No datasets found
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                        Upload your first dataset to get started
                    </Typography>
                </Box>
            ) : (
                <Grid container spacing={3}>
                    {(items || []).map((dataset: Dataset) => (
                        <Grid size={{ xs: 12, sm: 6, md: 4 }} key={dataset.id}>
                            <Card>
                                <CardContent>
                                    <Typography variant="h6" gutterBottom noWrap>
                                        {dataset.name}
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                        {dataset.description || 'No description'}
                                    </Typography>
                                    <Box sx={{ mb: 1 }}>
                                        <Chip
                                            label={dataset.status || 'ready'}
                                            size="small"
                                            color={dataset.status === 'ready' ? 'success' : 'default'}
                                            sx={{ mr: 1 }}
                                        />
                                        <Chip
                                            label={(dataset.file_format || 'csv').toUpperCase()}
                                            size="small"
                                            variant="outlined"
                                        />
                                    </Box>
                                    <Typography variant="caption" display="block">
                                        Rows: {(dataset.row_count || 0).toLocaleString()}
                                    </Typography>
                                    <Typography variant="caption" display="block">
                                        Size: {formatBytes(dataset.size_bytes || 0)}
                                    </Typography>
                                    <Typography variant="caption" display="block">
                                        Created: {formatDate(dataset.created_at)}
                                    </Typography>
                                </CardContent>
                                <CardActions>
                                    <Button size="small" onClick={() => navigate(`/datasets/${dataset.id}`)}>
                                        View Details
                                    </Button>
                                </CardActions>
                            </Card>
                        </Grid>
                    ))}
                </Grid>
            )}

            {pagination.pages > 1 && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                    <Button
                        disabled={pagination.page === 1}
                        onClick={() => dispatch(setPagination({ page: pagination.page - 1 }))}
                    >
                        Previous
                    </Button>
                    <Typography sx={{ mx: 2, alignSelf: 'center' }}>
                        Page {pagination.page} of {pagination.pages}
                    </Typography>
                    <Button
                        disabled={pagination.page === pagination.pages}
                        onClick={() => dispatch(setPagination({ page: pagination.page + 1 }))}
                    >
                        Next
                    </Button>
                </Box>
            )}
        </Box>
    );
};

export default DatasetListPage;
