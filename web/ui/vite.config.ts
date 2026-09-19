import path from 'node:path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import { mockApi } from './dev/mock-api.ts'

// The built files are served by FastAPI from /, and the API is on /api. In
// `npm run dev` the API is proxied to the Python server so both run together.
// `MOCK=1 npm run dev` serves fixtures instead (dev/mock-api.ts), for designing without a model.
const mock = !!process.env.MOCK

export default defineConfig({
  plugins: [react(), tailwindcss(), ...(mock ? [mockApi()] : [])],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  server: { proxy: mock ? {} : { '/api': 'http://127.0.0.1:8001' } },
})
