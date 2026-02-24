import React, { useEffect } from 'react';
import {
    Container,
    Typography,
    Box,
    Paper,
    Grid,
    Card,
    CardContent,
    List,
    ListItem,
    ListItemText,
    IconButton,
    Divider,
    Button,
    Chip,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Stack,
    Alert,
    CircularProgress,
} from '@mui/material';
import {
    People as PeopleIcon,
    Storage as StorageIcon,
    Security as SecurityIcon,
    Delete as DeleteIcon,
    Settings as SettingsIcon,
    CheckCircle as CheckCircleIcon,
    Error as ErrorIcon,
} from '@mui/icons-material';
import { useAppDispatch, useAppSelector } from '../../store/hooks';
import { fetchDatasets } from '../../store/slices/datasetsSlice';
import { fetchAdminStats, fetchUsers, clearCache } from '../../store/slices/adminSlice';
import { useSnackbar } from 'notistack';
import LoadingSpinner from '../../components/common/LoadingSpinner';

const AdminPanelPage: React.FC = () => {
    const dispatch = useAppDispatch();
    const { enqueueSnackbar } = useSnackbar();
    const { items, loading: datasetsLoading } = useAppSelector((state) => state.datasets);
    const { stats, users, loading: adminLoading } = useAppSelector((state) => state.admin);

    useEffect(() => {
        dispatch(fetchDatasets({ page: 1, page_size: 100 }));
        dispatch(fetchAdminStats());
        dispatch(fetchUsers({}));
    }, [dispatch]);

    const handleClearCache = async () => {
        try {
            await dispatch(clearCache()).unwrap();
            enqueueSnackbar('Cache cleared successfully', { variant: 'success' });
        } catch (err: any) {
            enqueueSnackbar(err || 'Failed to clear cache', { variant: 'error' });
        }
    };

    const formatBytes = (bytes: number): string => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
    };

    if (datasetsLoading && items.length === 0 && !stats) {
        return <LoadingSpinner fullScreen />;
    }

    return (
        <Container maxWidth="lg" sx={{ py: 4 }}>
            <Box sx={{ mb: 4 }}>
                <Typography variant="h4" component="h1" gutterBottom fontWeight="bold">
                    Admin Panel
                </Typography>
                <Typography variant="body1" color="text.secondary">
                    System management and global overview.
                </Typography>
            </Box>

            <Grid container spacing={3} sx={{ mb: 4 }}>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Card sx={{ bgcolor: 'primary.50' }}>
                        <CardContent>
                            <Stack direction="row" spacing={2} alignItems="center">
                                <PeopleIcon color="primary" />
                                <Box>
                                    <Typography variant="caption" color="text.secondary">TOTAL USERS</Typography>
                                    <Typography variant="h5" fontWeight="bold">
                                        {adminLoading ? <CircularProgress size={20} /> : (stats?.total_users ?? '—')}
                                    </Typography>
                                </Box>
                            </Stack>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Card sx={{ bgcolor: 'secondary.50' }}>
                        <CardContent>
                            <Stack direction="row" spacing={2} alignItems="center">
                                <StorageIcon color="secondary" />
                                <Box>
                                    <Typography variant="caption" color="text.secondary">TOTAL DATASETS</Typography>
                                    <Typography variant="h5" fontWeight="bold">
                                        {stats?.total_datasets ?? items.length}
                                    </Typography>
                                </Box>
                            </Stack>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Card sx={{ bgcolor: 'info.50' }}>
                        <CardContent>
                            <Stack direction="row" spacing={2} alignItems="center">
                                <SecurityIcon color="info" />
                                <Box>
                                    <Typography variant="caption" color="text.secondary">SYSTEM STATUS</Typography>
                                    <Typography
                                        variant="h5"
                                        fontWeight="bold"
                                        sx={{ color: stats?.system_status === 'Healthy' ? 'success.main' : 'warning.main' }}
                                    >
                                        {stats?.system_status ?? 'Unknown'}
                                    </Typography>
                                </Box>
                            </Stack>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Card sx={{ bgcolor: 'warning.50' }}>
                        <CardContent>
                            <Stack direction="row" spacing={2} alignItems="center">
                                <StorageIcon color="warning" />
                                <Box>
                                    <Typography variant="caption" color="text.secondary">STORAGE USED</Typography>
                                    <Typography variant="h5" fontWeight="bold">
                                        {stats ? formatBytes(stats.total_storage_bytes) : '—'}
                                    </Typography>
                                </Box>
                            </Stack>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            <Grid container spacing={4}>
                <Grid size={{ xs: 12, md: 8 }}>
                    <Paper sx={{ p: 3, borderRadius: 2 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                            <Typography variant="h6" fontWeight="bold">Global Dataset Management</Typography>
                            <Button size="small" variant="outlined">View All</Button>
                        </Box>
                        <TableContainer>
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Dataset Name</TableCell>
                                        <TableCell>Owner</TableCell>
                                        <TableCell>Status</TableCell>
                                        <TableCell align="right">Actions</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {items.slice(0, 10).map((dataset) => (
                                        <TableRow key={dataset.id}>
                                            <TableCell sx={{ fontWeight: 500 }}>{dataset.name}</TableCell>
                                            <TableCell>{dataset.owner}</TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={dataset.status}
                                                    size="small"
                                                    color={dataset.status === 'ready' ? 'success' : 'default'}
                                                    variant="outlined"
                                                />
                                            </TableCell>
                                            <TableCell align="right">
                                                <IconButton size="small"><SettingsIcon fontSize="small" /></IconButton>
                                                <IconButton size="small" color="error"><DeleteIcon fontSize="small" /></IconButton>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </Paper>

                    {/* User Management Table */}
                    {users.length > 0 && (
                        <Paper sx={{ p: 3, borderRadius: 2, mt: 3 }}>
                            <Typography variant="h6" fontWeight="bold" gutterBottom>
                                User Management
                            </Typography>
                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Email</TableCell>
                                            <TableCell>Role</TableCell>
                                            <TableCell>Registered</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {users.map((user) => (
                                            <TableRow key={user.email}>
                                                <TableCell sx={{ fontWeight: 500 }}>{user.email}</TableCell>
                                                <TableCell>
                                                    <Chip
                                                        label={user.role}
                                                        size="small"
                                                        color={user.role === 'admin' ? 'error' : user.role === 'contributor' ? 'primary' : 'default'}
                                                        variant="outlined"
                                                    />
                                                </TableCell>
                                                <TableCell>
                                                    {user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </Paper>
                    )}
                </Grid>

                <Grid size={{ xs: 12, md: 4 }}>
                    <Paper sx={{ p: 3, borderRadius: 2, mb: 3 }}>
                        <Typography variant="h6" fontWeight="bold" gutterBottom>System Alerts</Typography>
                        <Stack spacing={2}>
                            {stats?.system_status === 'Healthy' ? (
                                <Alert severity="success" icon={<CheckCircleIcon fontSize="inherit" />}>
                                    All systems are operating normally.
                                </Alert>
                            ) : (
                                <Alert severity="warning" icon={<ErrorIcon fontSize="inherit" />}>
                                    System status: {stats?.system_status || 'Unknown'}
                                </Alert>
                            )}
                        </Stack>
                    </Paper>

                    <Paper sx={{ p: 3, borderRadius: 2 }}>
                        <Typography variant="h6" fontWeight="bold" gutterBottom>Quick Actions</Typography>
                        <Stack spacing={1}>
                            <Button
                                fullWidth
                                variant="outlined"
                                startIcon={<PeopleIcon />}
                                onClick={() => dispatch(fetchUsers({}))}
                            >
                                Refresh Users
                            </Button>
                            <Button
                                fullWidth
                                variant="outlined"
                                startIcon={<SettingsIcon />}
                                onClick={() => dispatch(fetchAdminStats())}
                            >
                                Refresh Stats
                            </Button>
                            <Button
                                fullWidth
                                variant="outlined"
                                color="error"
                                startIcon={<DeleteIcon />}
                                onClick={handleClearCache}
                            >
                                Clear Temporary Cache
                            </Button>
                        </Stack>
                    </Paper>
                </Grid>
            </Grid>
        </Container>
    );
};

export default AdminPanelPage;
