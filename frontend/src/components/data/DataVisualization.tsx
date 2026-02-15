import React, { useMemo } from 'react';
import {
    Box,
    Typography,
    Paper,
    Grid,
    Card,
    CardContent,
    Stack,
    Divider,
} from '@mui/material';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell,
} from 'recharts';
import { Dataset, DatasetRow, DatasetStatistics } from '../../types/dataset.types';

interface DataVisualizationProps {
    dataset: Dataset;
    rows: DatasetRow[];
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8'];

export const DataVisualization: React.FC<DataVisualizationProps> = ({ dataset, rows }) => {

    // Calculate column type distribution
    const columnStats = useMemo(() => {
        if (!rows || rows.length === 0) return [];

        const firstRow = rows[0];
        const types: Record<string, number> = {};

        Object.values(firstRow).forEach(val => {
            const type = typeof val;
            types[type] = (types[type] || 0) + 1;
        });

        return Object.entries(types).map(([name, value]) => ({ name, value }));
    }, [rows]);

    // Calculate null values per column
    const nullStats = useMemo(() => {
        if (!rows || rows.length === 0) return [];

        const cols = Object.keys(rows[0] || {});
        return cols.map(col => {
            const nullCount = rows.filter(row => row[col] === null || row[col] === undefined || row[col] === '').length;
            return {
                name: col,
                nulls: nullCount,
                purity: ((rows.length - nullCount) / rows.length) * 100
            };
        }).sort((a, b) => b.nulls - a.nulls).slice(0, 10);
    }, [rows]);

    return (
        <Grid container spacing={3}>
            {/* Summary Cards */}
            <Grid size={12}>
                <Stack direction="row" spacing={3} sx={{ mb: 2 }}>
                    <Card sx={{ flex: 1, bgcolor: 'primary.50' }}>
                        <CardContent>
                            <Typography color="text.secondary" variant="caption" fontWeight="bold">TOTAL ROWS</Typography>
                            <Typography variant="h4" fontWeight="bold" color="primary.main">
                                {dataset.row_count.toLocaleString()}
                            </Typography>
                        </CardContent>
                    </Card>
                    <Card sx={{ flex: 1, bgcolor: 'secondary.50' }}>
                        <CardContent>
                            <Typography color="text.secondary" variant="caption" fontWeight="bold">TOTAL COLUMNS</Typography>
                            <Typography variant="h4" fontWeight="bold" color="secondary.main">
                                {rows && rows.length > 0 ? Object.keys(rows[0]).length : 0}
                            </Typography>
                        </CardContent>
                    </Card>
                    <Card sx={{ flex: 1, bgcolor: 'warning.50' }}>
                        <CardContent>
                            <Typography color="text.secondary" variant="caption" fontWeight="bold">DATA QUALITY (FILL RATE)</Typography>
                            <Typography variant="h4" fontWeight="bold" color="warning.main">
                                {nullStats.length > 0 ? (nullStats.reduce((acc, curr) => acc + curr.purity, 0) / nullStats.length).toFixed(1) : 0}%
                            </Typography>
                        </CardContent>
                    </Card>
                </Stack>
            </Grid>

            {/* Column Type Distribution */}
            <Grid size={{ xs: 12, md: 5 }}>
                <Paper sx={{ p: 3, height: '100%', borderRadius: 2 }}>
                    <Typography variant="h6" gutterBottom fontWeight="bold">
                        Column Data Types
                    </Typography>
                    <Box sx={{ height: 300 }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie
                                    data={columnStats}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={60}
                                    outerRadius={80}
                                    fill="#8884d8"
                                    paddingAngle={5}
                                    dataKey="value"
                                    label
                                >
                                    {columnStats.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                    ))}
                                </Pie>
                                <Tooltip />
                                <Legend />
                            </PieChart>
                        </ResponsiveContainer>
                    </Box>
                </Paper>
            </Grid>

            {/* Data Purity (Top 10 columns by null count) */}
            <Grid size={{ xs: 12, md: 7 }}>
                <Paper sx={{ p: 3, height: '100%', borderRadius: 2 }}>
                    <Typography variant="h6" gutterBottom fontWeight="bold">
                        Top 10 Column Completion (Fill Rate)
                    </Typography>
                    <Box sx={{ height: 300 }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart
                                data={nullStats}
                                layout="vertical"
                                margin={{ top: 5, right: 30, left: 40, bottom: 5 }}
                            >
                                <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} />
                                <XAxis type="number" domain={[0, 100]} unit="%" />
                                <YAxis dataKey="name" type="category" width={100} />
                                <Tooltip formatter={(value: number) => [`${value.toFixed(1)}%`, 'Fill Rate']} />
                                <Bar dataKey="purity" fill="#388e3c" radius={[0, 4, 4, 0]} barSize={20} />
                            </BarChart>
                        </ResponsiveContainer>
                    </Box>
                </Paper>
            </Grid>
        </Grid>
    );
};
