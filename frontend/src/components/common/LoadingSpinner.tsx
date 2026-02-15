import { CircularProgress, Box } from '@mui/material';

interface LoadingSpinnerProps {
    size?: number;
    fullScreen?: boolean;
}

const LoadingSpinner = ({ size = 40, fullScreen = false }: LoadingSpinnerProps) => {
    if (fullScreen) {
        return (
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    minHeight: '100vh',
                }}
            >
                <CircularProgress size={size} />
            </Box>
        );
    }

    return (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress size={size} />
        </Box>
    );
};

export default LoadingSpinner;
