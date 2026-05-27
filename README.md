# ANPR.OS — Automatic Number Plate Recognition & Parking System

Production-grade ANPR and parking management system powered by FastAPI, React (Vite), Redis, PostgreSQL, and OpenVINO/PaddleOCR.

---

## Option 1: Docker Setup (Recommended / Quickest)

Runs all services (PostgreSQL, Redis, OCR Engine, Backend API, OCR Worker, and Frontend UI) in self-contained containers.

### 1. Prerequisites
Ensure you have Docker and Docker Compose installed on your Linux machine:
```bash
sudo apt update
sudo apt install docker.io docker-compose -y
sudo systemctl enable --now docker
```

### 2. Start the Stack
From the project root directory, run:
```bash
docker-compose up -d --build
```

### 3. Verify Running Services
```bash
docker-compose ps
```
*   **Frontend Dashboard**: http://localhost
*   **Backend API Docs**: http://localhost:8000/docs
*   **OCR Microservice**: http://localhost:8001

### 4. Stop the Stack
```bash
docker-compose down
```

---

## Option 2: Native Linux & PostgreSQL Setup (Development)

Follow this setup to run each service natively on your Linux machine.

### 1. Prerequisites Installation
Install system dependencies (Redis, OpenCV requirements, Node.js, and PostgreSQL):
```bash
# Update package repositories
sudo apt update

# Install PostgreSQL & Redis
sudo apt install postgresql postgresql-contrib redis-server -y
sudo systemctl enable --now postgresql redis-server

# Install Python & build dependencies (needed for OpenCV / OCR)
sudo apt install python3-pip python3-venv libgl1-mesa-glx libglib2.0-0 -y

# Install Node.js (v18+) & NPM for the frontend
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install nodejs -y
```

### 2. PostgreSQL Configuration
Configure the local PostgreSQL instance to match the credentials defined in [`.env`](file:///d:/ANPR/.env):

```bash
# Log in to PostgreSQL as default superuser
sudo -u postgres psql
```

Inside the `psql` shell, execute:
```sql
-- Create database user
CREATE USER postgres WITH PASSWORD 'as your password entered sir ';

-- Create the database named "post"
CREATE DATABASE post OWNER postgres;

-- Exit the shell
\q
```

Verify connection using:
```bash
PGPASSWORD='the thing you entered' psql -h localhost -U postgres -d post
```

### 3. Environment Variables (`.env`)
Make sure the [`.env`](file:///d:/ANPR/.env) file at the root of the project contains the correct connection details:
```ini
DATABASE_URL=postgresql://postgres:visithran%40123@localhost:5432/post
REDIS_URL=redis://localhost:6379/0
```

### 4. Python Backend & OCR Services Setup
Run these commands from the root directory:

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install requirements
pip install --upgrade pip
pip install -r requirements.txt

# Start Backend, OCR Microservice, and OCR Worker simultaneously
python scripts/start_all.py
```
*Note: `start_all.py` automatically initializes database tables on first launch.*

### 5. Frontend Client Setup
Run these commands from the `frontend/` directory to launch the web client:

```bash
# Navigate to frontend folder
cd frontend

# Install Node dependencies
npm install

# Start Vite development server
npm run dev
```
*   **Web Console**: http://localhost:5173 (or the port outputted in the CLI)

---

## Project Commands Reference

| Service / Command | Purpose | Directory |
| :--- | :--- | :--- |
| `docker-compose up -d` | Launch all containers in background | `/` |
| `docker-compose logs -f <service>` | Stream logs for `backend`, `frontend`, `ocr`, `postgres`, `redis`, or `ocr_worker` | `/` |
| `python scripts/start_all.py` | Run local python Backend, OCR service, and Worker process manager | `/` |
| `npm run dev` | Run Vite frontend dashboard locally | `/frontend` |
| `npm run build` | Build static production assets for Nginx/Vite | `/frontend` |
| `alembic upgrade head` | Apply database migrations manually | `/` |
