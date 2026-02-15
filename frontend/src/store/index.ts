import { configureStore } from '@reduxjs/toolkit';
import authReducer from './slices/authSlice';
import datasetsReducer from './slices/datasetsSlice';

export const store = configureStore({
    reducer: {
        auth: authReducer,
        datasets: datasetsReducer,
    },
    middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware({
            serializableCheck: {
                // Ignore these action types
                ignoredActions: ['datasets/uploadDataset/pending'],
                // Ignore these field paths in all actions
                ignoredActionPaths: ['payload.file'],
                // Ignore these paths in the state
                ignoredPaths: ['datasets.uploadData.file'],
            },
        }),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
