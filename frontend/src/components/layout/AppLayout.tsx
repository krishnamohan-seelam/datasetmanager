import { Outlet } from 'react-router-dom';
import { Box, Container } from '@mui/material';
import { SnackbarProvider } from 'notistack';
import Header from './Header';

const AppLayout = () => {
    return (
        <SnackbarProvider maxSnack={3} anchorOrigin={{ vertical: 'top', horizontal: 'right' }}>
            <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
                <Header />
                <Container maxWidth="xl" sx={{ mt: 4, mb: 4, flexGrow: 1 }}>
                    <Outlet />
                </Container>
            </Box>
        </SnackbarProvider>
    );
};

export default AppLayout;
