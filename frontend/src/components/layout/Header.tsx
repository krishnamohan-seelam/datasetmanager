import { AppBar, Toolbar, Typography, Button, Box } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../store/hooks';
import { logout } from '../../store/slices/authSlice';

const Header = () => {
    const navigate = useNavigate();
    const dispatch = useAppDispatch();
    const { user, isAuthenticated } = useAppSelector((state) => state.auth);

    const handleLogout = () => {
        dispatch(logout());
        navigate('/login');
    };

    return (
        <AppBar position="static">
            <Toolbar>
                <Typography
                    variant="h6"
                    component="div"
                    sx={{ flexGrow: 1, cursor: 'pointer' }}
                    onClick={() => navigate('/')}
                >
                    {import.meta.env.VITE_APP_NAME as string || 'Dataset Manager'}
                </Typography>

                {isAuthenticated && user && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Typography variant="body2">
                            {user.email} ({user.role})
                        </Typography>
                        <Button color="inherit" onClick={() => navigate('/datasets/upload')}>
                            Upload Dataset
                        </Button>
                        {user.role === 'admin' && (
                            <Button color="inherit" onClick={() => navigate('/admin')}>
                                Admin
                            </Button>
                        )}
                        <Button color="inherit" onClick={handleLogout}>
                            Logout
                        </Button>
                    </Box>
                )}
            </Toolbar>
        </AppBar>
    );
};

export default Header;
