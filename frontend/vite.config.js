import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: "firebase-firestore",
              test: /node_modules[\\/]@firebase[\\/]firestore/,
            },
            {
              name: "firebase-auth",
              test: /node_modules[\\/]@firebase[\\/]auth/,
            },
            {
              name: "firebase-core",
              test: /node_modules[\\/](?:@firebase|firebase)[\\/]/,
            },
            {
              name: "react-vendor",
              test: /node_modules[\\/](?:react|react-dom|react-router-dom)[\\/]/,
            },
          ],
        },
      },
    },
  },
})
