import React, { useEffect, useState } from 'react';
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
    ListItemSecondaryAction,
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
import LoadingSpinner from '../../components/common/LoadingSpinner';

const AdminPanelPage: React.FC = () => {
    const dispatch = useAppDispatch();
    const { items, loading, pagination } = useAppSelector((state) => state.datasets);

    // In a real app, these would come from an admin API
    const stats = {
        totalUsers: 42,
        totalDatasets: items.length,
        systemStatus: 'Healthy',
        storageUsed: '1.2 TB'
    };

    useEffect(() => {
        dispatch(fetchDatasets({ page: 1, page_size: 100 }));
    }, [dispatch]);

    if (loading && items.length === 0) {
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
                                    <Typography variant="h5" fontWeight="bold">42</Typography>
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
                                    <Typography variant="h5" fontWeight="bold">{items.length}</Typography>
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
                                    <Typography variant="h5" fontWeight="bold" sx={{ color: 'success.main' }}>Healthy</Typography>
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
                                    <Typography variant="h5" fontWeight="bold">1.2 TB</Typography>
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
                </Grid>

                <Grid size={{ xs: 12, md: 4 }}>
                    <Paper sx={{ p: 3, borderRadius: 2, mb: 3 }}>
                        <Typography variant="h6" fontWeight="bold" gutterBottom>System Alerts</Typography>
                        <Stack spacing={2}>
                            <Alert severity="info" icon={<CheckCircleIcon fontSize="inherit" />}>
                                Weekly backup completed successfully.
                            </Alert>
                            <Alert severity="warning">
                                Storage usage exceeded 80% on Node-3.
                            </Alert>
                            <Alert severity="error" icon={<ErrorIcon fontSize="inherit" />}>
                                Dataset extraction failed for 'BigData_Test_v2'.
                            </Alert>
                        </Stack>
                    </Paper>

                    <Paper sx={{ p: 3, borderRadius: 2 }}>
                        <Typography variant="h6" fontWeight="bold" gutterBottom>Quick Actions</Typography>
                        <Stack spacing={1}>
                            <Button fullWidth variant="outlined" startIcon={<PeopleIcon />}>Manage Users</Button>
                            <Button fullWidth variant="outlined" startIcon={<SettingsIcon />}>System Settings</Button>
                            <Button fullWidth variant="outlined" color="error" startIcon={<DeleteIcon />}>Clear Temporary Cache</Button>
                        </Stack>
                    </Paper>
                </Grid>
            </Grid>
        </Container>
    );
};

export default AdminPanelPage;
