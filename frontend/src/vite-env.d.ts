/// <reference types="vite/client" />

interface ImportMetaEnv {
    readonly VITE_API_BASE_URL: string;
    readonly VITE_APP_NAME: string;
    readonly VITE_UPLOAD_MAX_SIZE: string;
}

interface ImportMeta {
    readonly env: ImportMetaEnv;
}
