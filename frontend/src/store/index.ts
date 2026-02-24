import { configureStore } from '@reduxjs/toolkit';
import authReducer from './slices/authSlice';
import datasetsReducer from './slices/datasetsSlice';
import adminReducer from './slices/adminSlice';

export const store = configureStore({
    reducer: {
        auth: authReducer,
        datasets: datasetsReducer,
        admin: adminReducer,
    },
    middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware({
            serializableCheck: {
                // Ignore these action types
                ignoredActions: [
                    'datasets/uploadDataset/pending',
                    'datasets/downloadDataset/fulfilled',
                ],
                // Ignore these field paths in all actions
                ignoredActionPaths: ['payload.file'],
                // Ignore these paths in the state
                ignoredPaths: ['datasets.uploadData.file'],
            },
        }),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
