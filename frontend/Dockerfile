FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

# Start the Vite development server and expose it to the host
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
