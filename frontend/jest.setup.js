import '@testing-library/jest-dom';

// Set API URL for tests to avoid "Invalid URL" errors with relative paths in Node.js environment
process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000';
