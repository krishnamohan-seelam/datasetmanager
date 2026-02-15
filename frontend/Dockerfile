# Development Dockerfile for Frontend
FROM node:20-slim

WORKDIR /app

# Install dependencies first (for better caching)
COPY package*.json ./
RUN npm install

# Copy the rest of the application
COPY . .

# Expose Vite's default dev port
EXPOSE 5173

# Run in host mode so it's accessible from the browser
CMD ["npm", "run", "dev", "--", "--host"]
