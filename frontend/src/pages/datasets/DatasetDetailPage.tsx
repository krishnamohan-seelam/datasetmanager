import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Container,
    Box,
    Typography,
    Paper,
    Grid,
    Button,
    Chip,
    Divider,
    Tabs,
    Tab,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    IconButton,
    Breadcrumbs,
    Link,
    Alert,
    Stack,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    FormControlLabel,
    Switch,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    List,
    ListItem,
    ListItemText,
    ListItemSecondaryAction,
    Avatar,
} from '@mui/material';
import {
    Download as DownloadIcon,
    Edit as EditIcon,
    Delete as DeleteIcon,
    ArrowBack as ArrowBackIcon,
    Storage as StorageIcon,
    AccessTime as TimeIcon,
    Person as PersonIcon,
    Share as ShareIcon,
    Refresh as RefreshIcon,
    ShieldOutlined as ShieldIcon,
} from '@mui/icons-material';
import { useAppDispatch, useAppSelector } from '../../store/hooks';
import {
    fetchDataset,
    fetchDatasetRows,
    clearCurrentDataset,
    updateDataset,
    deleteDataset,
    fetchPermissions,
    grantPermission,
    revokePermission,
    fetchSchema,
    updateMaskingRule,
} from '../../store/slices/datasetsSlice';
import { useSnackbar } from 'notistack';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import { DataVisualization } from '../../components/data/DataVisualization';

interface TabPanelProps {
    children?: React.ReactNode;
    index: number;
    value: number;
}

function TabPanel(props: TabPanelProps) {
    const { children, value, index, ...other } = props;
    return (
        <div
            role="tabpanel"
            hidden={value !== index}
            id={`dataset-tabpanel-${index}`}
            aria-labelledby={`dataset-tab-${index}`}
            {...other}
        >
            {value === index && (
                <Box sx={{ py: 3 }}>
                    {children}
                </Box>
            )}
        </div>
    );
}

const DatasetDetailPage: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const dispatch = useAppDispatch();
    const { enqueueSnackbar } = useSnackbar();
    const {
        currentDataset,
        currentDatasetRows,
        currentDatasetPermissions,
        currentDatasetSchema,
        rowsPagination,
        loading,
        error,
    } = useAppSelector((state) => state.datasets);

    const [tabValue, setTabValue] = useState(0);
    const [editOpen, setEditOpen] = useState(false);
    const [editData, setEditData] = useState({
        name: '',
        description: '',
        is_public: false,
    });
    const [shareOpen, setShareOpen] = useState(false);
    const [shareEmail, setShareEmail] = useState('');
    const [shareRole, setShareRole] = useState<'contributor' | 'viewer'>('viewer');

    useEffect(() => {
        if (id) {
            dispatch(fetchDataset(id));
            dispatch(fetchDatasetRows({ datasetId: id, params: { ...rowsPagination } }));
            dispatch(fetchSchema(id));
        }
        return () => {
            dispatch(clearCurrentDataset());
        };
    }, [id, dispatch]);

    useEffect(() => {
        if (currentDataset) {
            setEditData({
                name: currentDataset.name,
                description: currentDataset.description || '',
                is_public: currentDataset.is_public,
            });
        }
    }, [currentDataset]);

    const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
        setTabValue(newValue);
    };

    const handleShareOpen = () => {
        if (id) {
            dispatch(fetchPermissions(id));
            setShareOpen(true);
        }
    };

    const handleShareClose = () => {
        setShareOpen(false);
        setShareEmail('');
        setShareRole('viewer');
    };

    const handleGrantPermission = async () => {
        if (!id || !shareEmail) return;
        try {
            await dispatch(grantPermission({
                datasetId: id,
                userEmail: shareEmail,
                role: shareRole
            })).unwrap();
            enqueueSnackbar('Permission granted successfully', { variant: 'success' });
            setShareEmail('');
        } catch (err: any) {
            enqueueSnackbar(err || 'Failed to grant permission', { variant: 'error' });
        }
    };

    const handleRevokePermission = async (email: string) => {
        if (!id) return;
        try {
            await dispatch(revokePermission({
                datasetId: id,
                userEmail: email
            })).unwrap();
            enqueueSnackbar('Permission revoked', { variant: 'success' });
        } catch (err: any) {
            enqueueSnackbar(err || 'Failed to revoke permission', { variant: 'error' });
        }
    };

    const handleRefresh = () => {
        if (id) {
            dispatch(fetchDataset(id));
            dispatch(fetchDatasetRows({ datasetId: id, params: { ...rowsPagination } }));
        }
    };

    const handleUpdate = async () => {
        if (!id) return;
        try {
            await dispatch(updateDataset({ id, updates: editData })).unwrap();
            enqueueSnackbar('Dataset updated successfully', { variant: 'success' });
            setEditOpen(false);
        } catch (err: any) {
            enqueueSnackbar(err || 'Failed to update dataset', { variant: 'error' });
        }
    };

    const handleUpdateMasking = async (columnName: string, rule: string | null) => {
        if (!id) return;
        try {
            await dispatch(updateMaskingRule({
                datasetId: id,
                columnName,
                maskRule: rule
            })).unwrap();
            enqueueSnackbar(`Masking rule updated for ${columnName}`, { variant: 'success' });
        } catch (err: any) {
            enqueueSnackbar(err || 'Failed to update masking rule', { variant: 'error' });
        }
    };

    const handleDelete = async () => {
        if (!id) return;
        if (window.confirm('Are you sure you want to delete this dataset? This action cannot be undone.')) {
            try {
                await dispatch(deleteDataset(id)).unwrap();
                enqueueSnackbar('Dataset deleted successfully', { variant: 'success' });
                navigate('/datasets');
            } catch (err: any) {
                enqueueSnackbar(err || 'Failed to delete dataset', { variant: 'error' });
            }
        }
    };

    const formatBytes = (bytes: number): string => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    };

    const formatDate = (dateString: string): string => {
        return new Date(dateString).toLocaleString();
    };

    if (loading && !currentDataset) {
        return <LoadingSpinner fullScreen />;
    }

    if (error) {
        return (
            <Container sx={{ py: 4 }}>
                <Alert severity="error" sx={{ mb: 2 }}>
                    {error}
                </Alert>
                <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/datasets')}>
                    Back to Datasets
                </Button>
            </Container>
        );
    }

    if (!currentDataset) {
        return (
            <Container sx={{ py: 4 }}>
                <Typography>Dataset not found</Typography>
                <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/datasets')}>
                    Back to Datasets
                </Button>
            </Container>
        );
    }

    const columns = (currentDatasetRows?.length || 0) > 0 ? Object.keys(currentDatasetRows[0]) : [];

    return (
        <Container maxWidth="xl" sx={{ py: 4 }}>
            <Box sx={{ mb: 4 }}>
                <Breadcrumbs aria-label="breadcrumb" sx={{ mb: 2 }}>
                    <Link underline="hover" color="inherit" onClick={() => navigate('/datasets')} sx={{ cursor: 'pointer' }}>
                        Datasets
                    </Link>
                    <Typography color="text.primary">{currentDataset.name}</Typography>
                </Breadcrumbs>

                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2 }}>
                    <Box>
                        <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 1 }}>
                            <Typography variant="h4" component="h1" fontWeight="bold">
                                {currentDataset.name}
                            </Typography>
                            <Chip
                                label={currentDataset.status}
                                color={currentDataset.status === 'ready' ? 'success' : 'warning'}
                                size="small"
                                variant="outlined"
                            />
                            {currentDataset.is_public && (
                                <Chip label="Public" size="small" color="info" />
                            )}
                        </Stack>
                        <Typography variant="body1" color="text.secondary">
                            {currentDataset.description || 'No description provided.'}
                        </Typography>
                    </Box>

                    <Stack direction="row" spacing={1}>
                        <Button
                            variant="outlined"
                            startIcon={<RefreshIcon />}
                            onClick={handleRefresh}
                        >
                            Refresh
                        </Button>
                        <Button
                            variant="outlined"
                            startIcon={<EditIcon />}
                            onClick={() => setEditOpen(true)}
                        >
                            Edit
                        </Button>
                        <Button
                            variant="contained"
                            startIcon={<DownloadIcon />}
                            onClick={() => enqueueSnackbar('Download functionality coming soon', { variant: 'info' })}
                        >
                            Download
                        </Button>
                        <IconButton color="error" onClick={handleDelete}>
                            <DeleteIcon />
                        </IconButton>
                    </Stack>
                </Box>
            </Box>

            <Grid container spacing={4}>
                <Grid size={{ xs: 12, md: 8 }}>
                    <Paper sx={{ borderRadius: 2 }}>
                        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                            <Tabs value={tabValue} onChange={handleTabChange} aria-label="dataset tabs">
                                <Tab label="Data Preview" />
                                <Tab label="Analytics" />
                                <Tab label="Schema" />
                                <Tab label="Lineage & Usage" />
                            </Tabs>
                        </Box>

                        <TabPanel value={tabValue} index={0}>
                            {(currentDatasetRows?.length || 0) > 0 ? (
                                <TableContainer sx={{ maxHeight: 600 }}>
                                    <Table stickyHeader size="small">
                                        <TableHead>
                                            <TableRow>
                                                {columns.map((col) => (
                                                    <TableCell key={col} sx={{ fontWeight: 'bold' }}>
                                                        {col}
                                                    </TableCell>
                                                ))}
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {currentDatasetRows.map((row, idx) => (
                                                <TableRow key={idx} hover>
                                                    {columns.map((col) => (
                                                        <TableCell key={`${idx}-${col}`}>
                                                            {String(row[col])}
                                                        </TableCell>
                                                    ))}
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            ) : (
                                <Box sx={{ py: 8, textAlign: 'center' }}>
                                    <Typography color="text.secondary">
                                        No data available to preview.
                                    </Typography>
                                </Box>
                            )}
                        </TabPanel>

                        <TabPanel value={tabValue} index={1}>
                            <DataVisualization dataset={currentDataset} rows={currentDatasetRows} />
                        </TabPanel>

                        <TabPanel value={tabValue} index={2}>
                            <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <Typography variant="h6" fontWeight="bold">Dataset Schema & Masking</Typography>
                                <Chip label={`${currentDatasetSchema?.length || 0} Columns`} color="primary" variant="outlined" size="small" />
                            </Box>

                            <Alert severity="info" sx={{ mb: 3 }}>
                                Define masking rules for sensitive columns. Masking is applied in real-time for non-admin users.
                            </Alert>

                            <TableContainer component={Paper} variant="outlined">
                                <Table size="small">
                                    <TableHead sx={{ bgcolor: 'action.hover' }}>
                                        <TableRow>
                                            <TableCell sx={{ fontWeight: 'bold' }}>Column Name</TableCell>
                                            <TableCell sx={{ fontWeight: 'bold' }}>Type</TableCell>
                                            <TableCell sx={{ fontWeight: 'bold' }}>Masking Rule</TableCell>
                                            <TableCell sx={{ fontWeight: 'bold' }}>Status</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {(currentDatasetSchema || []).map((col) => (
                                            <TableRow key={col.name}>
                                                <TableCell sx={{ py: 1.5 }}>
                                                    <Typography variant="body2" fontWeight="medium">{col.name}</Typography>
                                                </TableCell>
                                                <TableCell>
                                                    <Chip label={col.type} size="small" variant="outlined" sx={{ fontSize: '0.7rem' }} />
                                                </TableCell>
                                                <TableCell>
                                                    <FormControl size="small" fullWidth sx={{ maxWidth: 200 }}>
                                                        <Select
                                                            value={col.mask_rule || 'none'}
                                                            onChange={(e) => {
                                                                const val = e.target.value;
                                                                handleUpdateMasking(col.name, val === 'none' ? null : val);
                                                            }}
                                                        >
                                                            <MenuItem value="none">None</MenuItem>
                                                            <MenuItem value="redact">Redact (Full)</MenuItem>
                                                            <MenuItem value="hash">Hash (SHA-256)</MenuItem>
                                                            <MenuItem value="partial_email">Partial (Email)</MenuItem>
                                                            <MenuItem value="partial_text">Partial (Text)</MenuItem>
                                                            <MenuItem value="numeric_round">Round (Numeric)</MenuItem>
                                                        </Select>
                                                    </FormControl>
                                                </TableCell>
                                                <TableCell>
                                                    {col.mask_rule ? (
                                                        <Chip
                                                            icon={<ShieldIcon sx={{ fontSize: '1rem !important' }} />}
                                                            label="Masked"
                                                            size="small"
                                                            color="success"
                                                            variant="outlined"
                                                        />
                                                    ) : (
                                                        <Typography variant="caption" color="text.disabled">No protection</Typography>
                                                    )}
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </TabPanel>

                        <TabPanel value={tabValue} index={3}>
                            <Typography variant="h6" gutterBottom fontWeight="bold">Lineage & Usage</Typography>
                            <Paper variant="outlined" sx={{ p: 4, textAlign: 'center', bgcolor: 'grey.50' }}>
                                <Typography color="text.secondary">
                                    Activity logs and dataset lineage tracking coming soon in v1.1.
                                </Typography>
                            </Paper>
                        </TabPanel>
                    </Paper>
                </Grid>

                <Grid size={{ xs: 12, md: 4 }}>
                    <Paper sx={{ p: 3, borderRadius: 2, mb: 3 }}>
                        <Typography variant="h6" gutterBottom fontWeight="bold">
                            Dataset Information
                        </Typography>
                        <Divider sx={{ mb: 2 }} />

                        <Stack spacing={2}>
                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                <StorageIcon sx={{ mr: 2, color: 'text.secondary' }} />
                                <Box>
                                    <Typography variant="caption" color="text.secondary" display="block">
                                        Format & Size
                                    </Typography>
                                    <Typography variant="body2">
                                        {(currentDataset.file_format || 'csv').toUpperCase()} • {formatBytes(currentDataset.size_bytes || 0)}
                                    </Typography>
                                </Box>
                            </Box>

                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                <TimeIcon sx={{ mr: 2, color: 'text.secondary' }} />
                                <Box>
                                    <Typography variant="caption" color="text.secondary" display="block">
                                        Created At
                                    </Typography>
                                    <Typography variant="body2">
                                        {formatDate(currentDataset.created_at)}
                                    </Typography>
                                </Box>
                            </Box>

                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                <PersonIcon sx={{ mr: 2, color: 'text.secondary' }} />
                                <Box>
                                    <Typography variant="caption" color="text.secondary" display="block">
                                        Owner
                                    </Typography>
                                    <Typography variant="body2">
                                        {currentDataset.owner}
                                    </Typography>
                                </Box>
                            </Box>

                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                <Typography variant="body2" sx={{ fontWeight: 'bold', minWidth: 40 }}>
                                    Rows
                                </Typography>
                                <Typography variant="body2" sx={{ ml: 2 }}>
                                    {currentDataset.row_count.toLocaleString()}
                                </Typography>
                            </Box>
                        </Stack>

                        <Typography variant="subtitle2" sx={{ mt: 3, mb: 1 }}>
                            Tags
                        </Typography>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                            {currentDataset.tags && (currentDataset.tags?.length || 0) > 0 ? (
                                currentDataset.tags.map(tag => (
                                    <Chip key={tag} label={tag} size="small" variant="outlined" />
                                ))
                            ) : (
                                <Typography variant="caption" color="text.secondary">No tags</Typography>
                            )}
                        </Box>
                    </Paper>

                    <Paper sx={{ p: 3, borderRadius: 2 }}>
                        <Typography variant="h6" gutterBottom fontWeight="bold">
                            Permissions
                        </Typography>
                        <Divider sx={{ mb: 2 }} />
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                            Manage who can access and edit this dataset.
                        </Typography>
                        <Button
                            fullWidth
                            variant="outlined"
                            startIcon={<ShareIcon />}
                            onClick={handleShareOpen}
                        >
                            Manage Permissions
                        </Button>
                    </Paper>
                </Grid>
            </Grid>

            {/* Edit Modal */}
            <Dialog open={editOpen} onClose={() => setEditOpen(false)} fullWidth maxWidth="sm">
                <DialogTitle>Edit Dataset Metadata</DialogTitle>
                <DialogContent>
                    <Stack spacing={3} sx={{ mt: 1 }}>
                        <TextField
                            label="Name"
                            fullWidth
                            value={editData.name}
                            onChange={(e) => setEditData({ ...editData, name: e.target.value })}
                        />
                        <TextField
                            label="Description"
                            fullWidth
                            multiline
                            rows={3}
                            value={editData.description}
                            onChange={(e) => setEditData({ ...editData, description: e.target.value })}
                        />
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={editData.is_public}
                                    onChange={(e) => setEditData({ ...editData, is_public: e.target.checked })}
                                />
                            }
                            label="Public Dataset"
                        />
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setEditOpen(false)}>Cancel</Button>
                    <Button onClick={handleUpdate} variant="contained" color="primary">Save Changes</Button>
                </DialogActions>
            </Dialog>

            {/* Share / Permissions Dialog */}
            <Dialog open={shareOpen} onClose={handleShareClose} fullWidth maxWidth="sm">
                <DialogTitle sx={{ fontWeight: 'bold' }}>Manage Permissions</DialogTitle>
                <DialogContent>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                        Add users by email to give them access to this dataset.
                    </Typography>

                    <Stack direction="row" spacing={2} sx={{ mb: 4 }}>
                        <TextField
                            label="User Email"
                            size="small"
                            fullWidth
                            value={shareEmail}
                            onChange={(e) => setShareEmail(e.target.value)}
                            placeholder="user@example.com"
                        />
                        <FormControl size="small" sx={{ minWidth: 120 }}>
                            <InputLabel>Role</InputLabel>
                            <Select
                                value={shareRole}
                                label="Role"
                                onChange={(e) => setShareRole(e.target.value as any)}
                            >
                                <MenuItem value="viewer">Viewer</MenuItem>
                                <MenuItem value="contributor">Contributor</MenuItem>
                            </Select>
                        </FormControl>
                        <Button
                            variant="contained"
                            onClick={handleGrantPermission}
                            disabled={!shareEmail}
                        >
                            Add
                        </Button>
                    </Stack>

                    <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
                        Current Permissions
                    </Typography>
                    <Paper variant="outlined" sx={{ borderRadius: 1 }}>
                        <List disablePadding>
                            {(currentDatasetPermissions?.length || 0) === 0 ? (
                                <ListItem>
                                    <ListItemText
                                        primary="No explicit permissions"
                                        secondary="Only the owner and admins can access this dataset unless it's public."
                                        primaryTypographyProps={{ variant: 'body2' }}
                                    />
                                </ListItem>
                            ) : (
                                (currentDatasetPermissions || []).map((permission, index) => (
                                    <React.Fragment key={permission.user_email}>
                                        <ListItem>
                                            <Avatar sx={{ mr: 2, bgcolor: 'primary.light', width: 32, height: 32, fontSize: '0.875rem' }}>
                                                {permission.user_email[0].toUpperCase()}
                                            </Avatar>
                                            <ListItemText
                                                primary={permission.user_email}
                                                secondary={permission.role.charAt(0).toUpperCase() + permission.role.slice(1)}
                                                primaryTypographyProps={{ variant: 'body2', fontWeight: 'medium' }}
                                            />
                                            <ListItemSecondaryAction>
                                                <IconButton
                                                    edge="end"
                                                    size="small"
                                                    color="error"
                                                    onClick={() => handleRevokePermission(permission.user_email)}
                                                >
                                                    <DeleteIcon fontSize="small" />
                                                </IconButton>
                                            </ListItemSecondaryAction>
                                        </ListItem>
                                        {index < (currentDatasetPermissions?.length || 0) - 1 && <Divider />}
                                    </React.Fragment>
                                ))
                            )}
                        </List>
                    </Paper>
                </DialogContent>
                <DialogActions sx={{ p: 3, pt: 0 }}>
                    <Button onClick={handleShareClose}>Close</Button>
                </DialogActions>
            </Dialog>
        </Container>
    );
};

export default DatasetDetailPage;
