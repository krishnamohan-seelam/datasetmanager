import { createBrowserRouter, Navigate } from 'react-router-dom';
import ProtectedRoute from './components/common/ProtectedRoute';
import AppLayout from './components/layout/AppLayout';
import LoginPage from './pages/auth/LoginPage';
import RegisterPage from './pages/auth/RegisterPage';
import DatasetListPage from './pages/datasets/DatasetListPage';
import DatasetUploadPage from './pages/datasets/DatasetUploadPage';
import DatasetDetailPage from './pages/datasets/DatasetDetailPage';
import AdminPanelPage from './pages/admin/AdminPanelPage';

export const router = createBrowserRouter([
    {
        path: '/login',
        element: <LoginPage />,
    },
    {
        path: '/register',
        element: <RegisterPage />,
    },
    {
        path: '/',
        element: (
            <ProtectedRoute>
                <AppLayout />
            </ProtectedRoute>
        ),
        children: [
            {
                index: true,
                element: <Navigate to="/datasets" replace />,
            },
            {
                path: 'datasets',
                children: [
                    {
                        index: true,
                        element: <DatasetListPage />,
                    },
                    {
                        path: 'upload',
                        element: <DatasetUploadPage />,
                    },
                    {
                        path: ':id',
                        element: <DatasetDetailPage />,
                    },
                ],
            },
            {
                path: 'admin',
                element: (
                    <ProtectedRoute requiredRole="admin">
                        <AdminPanelPage />
                    </ProtectedRoute>
                ),
            },
        ],
    },
]);
