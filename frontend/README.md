# Dataset Manager Frontend

React-based frontend application for the Dataset Manager Platform built with Vite, TypeScript, Material-UI, and Redux Toolkit.

## 🚀 Tech Stack

- **Framework**: React 18 with Vite
- **Language**: TypeScript
- **UI Library**: Material-UI (MUI) v5
- **State Management**: Redux Toolkit
- **Routing**: React Router v6
- **HTTP Client**: Axios
- **Form Handling**: React Hook Form + Zod
- **Notifications**: Notistack
- **Testing**: Vitest, React Testing Library, Playwright

## 📁 Project Structure

```
frontend/
├── src/
│   ├── api/                  # API client services
│   │   ├── axios.ts          # Axios instance with interceptors
│   │   ├── auth.api.ts       # Authentication API
│   │   └── datasets.api.ts   # Datasets API
│   ├── components/
│   │   ├── common/           # Reusable components
│   │   │   ├── LoadingSpinner.tsx
│   │   │   └── ProtectedRoute.tsx
│   │   └── layout/           # Layout components
│   │       ├── AppLayout.tsx
│   │       └── Header.tsx
│   ├── pages/
│   │   ├── auth/             # Authentication pages
│   │   │   ├── LoginPage.tsx
│   │   │   └── RegisterPage.tsx
│   │   └── datasets/         # Dataset pages
│   │       └── DatasetListPage.tsx
│   ├── store/                # Redux store
│   │   ├── slices/
│   │   │   ├── authSlice.ts
│   │   │   └── datasetsSlice.ts
│   │   ├── hooks.ts          # Typed Redux hooks
│   │   └── index.ts          # Store configuration
│   ├── types/                # TypeScript types
│   │   ├── common.types.ts
│   │   ├── dataset.types.ts
│   │   └── user.types.ts
│   ├── theme/                # MUI theme configuration
│   │   └── theme.ts
│   ├── router.tsx            # React Router configuration
│   ├── main.tsx              # Application entry point
│   └── vite-env.d.ts         # Vite environment types
├── .env.development          # Development environment variables
├── .env.production           # Production environment variables
├── .eslintrc.cjs             # ESLint configuration
├── .prettierrc               # Prettier configuration
├── tsconfig.json             # TypeScript configuration
├── vite.config.ts            # Vite configuration
└── package.json
```

## 🛠️ Setup & Installation

### Prerequisites

- Node.js 18+ and npm
- Backend API running (default: http://localhost:8000)

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## 🔧 Configuration

### Environment Variables

Create `.env.development` and `.env.production` files:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_NAME=Dataset Manager
VITE_UPLOAD_MAX_SIZE=10737418240
```

## 📋 Features Implemented

### ✅ Completed

1. **Project Setup**
   - Vite + React + TypeScript configuration
   - ESLint and Prettier setup
   - Environment variables configuration
   - MUI theme customization

2. **API Client Layer**
   - Axios instance with JWT interceptors
   - Request/response error handling
   - Authentication API (login, register, getCurrentUser)
   - Datasets API (CRUD operations, upload, download)
   - TypeScript type definitions

3. **State Management**
   - Redux Toolkit store configuration
   - Auth slice (login, register, logout, token management)
   - Datasets slice (fetch, upload, update, delete, pagination)
   - Typed Redux hooks

4. **Authentication & Authorization**
   - Login page with form validation
   - Registration page with role selection
   - Protected routes with role-based access control
   - JWT token storage and management
   - Auto-redirect on authentication failure

5. **Layout & Navigation**
   - App layout with header and navigation
   - Responsive design
   - User info display
   - Logout functionality

6. **Dataset Management**
   - Dataset list page with search and filtering
   - Pagination controls
   - Sort by multiple fields
   - Dataset cards with metadata display
   - Dataset detail page with metadata and lineage
   - Dataset editing (name, description, visibility)
   - Dataset deletion with confirmation

7. **Data Ingestion & Visualization**
   - Drag-and-drop file upload (CSV, JSON, Parquet)
   - Real-time upload progress and notifications
   - Interactive data preview table
   - Data visualization with charts (Recharts)
   - Column distribution and data quality analytics

8. **Admin Features**
   - Dedicated admin panel dashboard
   - Global system statistics (users, datasets, storage)
   - Centralized dataset management
   - System alerts and status monitoring

### 🚧 In Progress / TODO

- Permissions management UI (Sharing/RBAC)
- E2E tests with Playwright
- Performance optimization (code splitting, lazy loading)
- Dataset versioning and history tracking
- Advanced data masking configurations UI

## 🎨 UI/UX Features

- **Material Design**: Clean, modern UI with MUI components
- **Responsive**: Mobile-first design
- **Loading States**: Spinners and skeleton loaders
- **Error Handling**: User-friendly error messages
- **Notifications**: Toast notifications for user feedback
- **Accessibility**: ARIA labels and keyboard navigation

## 🔐 Security

- JWT token-based authentication
- Secure token storage in localStorage
- Automatic token refresh on API calls
- Protected routes with role-based access
- XSS protection through React's built-in escaping

## 🧪 Testing

```bash
# Run unit tests
npm run test

# Run E2E tests
npm run test:e2e

# Generate coverage report
npm run test:coverage
```

## 📝 Development Notes

### Known Issues

1. **MUI Grid Type Error**: Minor TypeScript error with MUI Grid component's `key` prop. This is a known MUI v5 issue and doesn't affect functionality. The app runs correctly in development mode.

### Code Style

- **ESLint**: Enforces code quality rules
- **Prettier**: Automatic code formatting
- **TypeScript**: Strict type checking (currently relaxed for initial development)

### State Management Patterns

- **Redux Toolkit**: Simplified Redux with createSlice and createAsyncThunk
- **Typed Hooks**: useAppDispatch and useAppSelector for type safety
- **Async Thunks**: For API calls with loading/error states

## 🚀 Deployment

```bash
# Build for production
npm run build

# The dist/ folder contains the production build
# Deploy to your hosting service (Vercel, Netlify, etc.)
```

## 📚 Additional Resources

- [React Documentation](https://react.dev/)
- [Vite Documentation](https://vitejs.dev/)
- [Material-UI Documentation](https://mui.com/)
- [Redux Toolkit Documentation](https://redux-toolkit.js.org/)
- [React Router Documentation](https://reactrouter.com/)

## 🤝 Contributing

1. Follow the existing code style
2. Write TypeScript types for all new code
3. Add tests for new features
4. Update documentation as needed

## 📄 License

This project is part of the Dataset Manager Platform.
