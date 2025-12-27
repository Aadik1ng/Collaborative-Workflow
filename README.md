# Real-Time Collaborative Workspace Backend

A production-ready backend service for a real-time collaborative workspace, featuring secure authentication, project management, and async job processing with actual code execution.

---

## 🏗️ Architecture Overview

```mermaid
graph LR
    subgraph Client
        A[Web/Mobile App]
    end

    subgraph API Gateway
        B[FastAPI]
    end

    subgraph Data Layer
        C[(PostgreSQL)]
        D[(MongoDB)]
        E[(Redis)]
    end

    subgraph Workers
        F[Celery Worker]
    end

    A -- REST/WebSocket --> B
    B -- Relational Data --> C
    B -- Job Results & Logs --> D
    B -- Cache & Pub/Sub --> E
    B -- Queue Tasks --> E
    F -- Consume Tasks --> E
    F -- Write Results --> D
```

### Component Breakdown

| Component        | Technology   | Purpose                                                         |
| :--------------- | :----------- | :-------------------------------------------------------------- |
| **API**          | FastAPI      | Handles HTTP requests, WebSocket connections, input validation. |
| **Auth**         | JWT + Argon2 | Secure access/refresh tokens, password hashing.                 |
| **SQL Store**    | PostgreSQL   | Persistent storage for users, projects, workspaces, roles.      |
| **NoSQL Store**  | MongoDB      | High-velocity data: job results, activity logs, events.         |
| **Cache/Broker** | Redis        | API caching, rate limiting, Pub/Sub for real-time sync.         |
| **Workers**      | Celery       | Asynchronous task execution (e.g., code execution jobs).        |

---

## 🚀 Setup & Run Instructions

### Prerequisites

- Python 3.11+
- PostgreSQL, MongoDB, Redis (running locally or via Docker)

### Option 1: Local Development

```bash
# 1. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your database credentials

# 4. Start the API server (Terminal 1)
uvicorn app.main:app --reload

# 5. Start the Celery worker (Terminal 2)
celery -A app.workers.celery_app worker --loglevel=info
```

### Option 2: Docker Compose

```bash
cd docker
docker-compose up -d
```

This starts:

- FastAPI API on port 8000
- Celery Worker
- PostgreSQL on port 5432
- MongoDB on port 27017
- Redis on port 6379
- Flower (Celery monitoring) on port 5555

### Accessing the API

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/v1/health

---

## 📐 Design Decisions & Trade-offs

### 1. Dual Database Strategy (PostgreSQL + MongoDB)

- **Why**: Relational data (users, projects, roles) benefits from ACID transactions and strict schemas. Non-relational data (job results, activity streams) requires high write throughput and flexible schemas.
- **Trade-off**: Added operational complexity of managing two databases.

### 2. Argon2 for Password Hashing

- **Why**: Argon2 is the winner of the Password Hashing Competition, resistant to GPU attacks, and avoids bcrypt's 72-byte limit.
- **Trade-off**: Slightly higher CPU usage per hash operation.

### 3. Celery for Async Jobs

- **Why**: Decouples long-running tasks (like code execution) from the request-response cycle, improving API responsiveness.
- **Trade-off**: Introduces Redis as a required dependency and adds deployment complexity.

### 4. JWT Authentication with Refresh Tokens

- **Why**: Stateless access tokens allow horizontal scaling of the API. Refresh tokens (stored in Redis) allow session invalidation.
- **Trade-off**: Requires careful handling of token expiry and refresh logic on the client.

### 5. WebSocket + Redis Pub/Sub for Real-Time Sync

- **Why**: Enables broadcasting of user cursors and document changes across multiple API instances.
- **Trade-off**: Redis becomes a central point of coordination; must be highly available.

### 6. Table Name Prefixing (`cw_`)

- **Why**: Allows this application to coexist with other applications using the same database by avoiding table name collisions (e.g., `cw_users` instead of `users`).
- **Trade-off**: Slightly longer table names in raw SQL queries.

---

## 📈 Scalability Considerations

### Horizontal Scaling

| Component          | Scaling Strategy                                                                          |
| :----------------- | :---------------------------------------------------------------------------------------- |
| **FastAPI**        | Deploy multiple instances behind a load balancer. All state lives in external stores.     |
| **Celery Workers** | Add more worker processes or pods. Use task routing to dedicated `code_execution` queues. |
| **PostgreSQL**     | Use read replicas for scaling reads. Consider connection pooling (e.g., PgBouncer).       |
| **MongoDB**        | Use sharding for write scaling. Replica sets for read scaling and availability.           |
| **Redis**          | Use Redis Cluster for high availability and scaling.                                      |

### Performance Optimizations

- **Rate Limiting**: A sliding-window rate limiter protects endpoints from abuse.
- **Caching**: Redis is used to cache frequently accessed data like user profiles.
- **Connection Pooling**: SQLAlchemy's async session pool efficiently manages DB connections.
- **Idempotent Jobs**: Job processing uses unique IDs to prevent duplicate work.

### Future Enhancements

- **Code Execution Sandboxing**: The current `subprocess` execution is for development only. Production requires Docker, Firecracker VMs, or gVisor for security.
- **Observability**: Integrate OpenTelemetry for distributed tracing across the API and workers.
- **Kubernetes Deployment**: Use Helm charts for managing deployments, scaling, and secrets.

---

## 📚 API Documentation

### Authentication Endpoints

| Method | Endpoint                | Description                  |
| :----- | :---------------------- | :--------------------------- |
| POST   | `/api/v1/auth/register` | Register a new user          |
| POST   | `/api/v1/auth/login`    | Login and get access token   |
| POST   | `/api/v1/auth/refresh`  | Refresh access token         |
| POST   | `/api/v1/auth/logout`   | Logout and invalidate tokens |
| GET    | `/api/v1/auth/me`       | Get current user profile     |
| PUT    | `/api/v1/auth/me`       | Update current user profile  |
| PUT    | `/api/v1/auth/password` | Change password              |

### Project Endpoints

| Method | Endpoint                | Description          |
| :----- | :---------------------- | :------------------- |
| POST   | `/api/v1/projects`      | Create a new project |
| GET    | `/api/v1/projects`      | List user's projects |
| GET    | `/api/v1/projects/{id}` | Get project details  |
| PUT    | `/api/v1/projects/{id}` | Update project       |
| DELETE | `/api/v1/projects/{id}` | Delete project       |

### Workspace Endpoints

| Method | Endpoint                           | Description             |
| :----- | :--------------------------------- | :---------------------- |
| POST   | `/api/v1/projects/{id}/workspaces` | Create a workspace      |
| GET    | `/api/v1/projects/{id}/workspaces` | List project workspaces |
| GET    | `/api/v1/workspaces/{id}`          | Get workspace details   |
| PUT    | `/api/v1/workspaces/{id}`          | Update workspace        |
| DELETE | `/api/v1/workspaces/{id}`          | Delete workspace        |

### Collaborator Endpoints

| Method | Endpoint                                        | Description                |
| :----- | :---------------------------------------------- | :------------------------- |
| POST   | `/api/v1/projects/{id}/collaborators`           | Invite a collaborator      |
| GET    | `/api/v1/projects/{id}/collaborators`           | List project collaborators |
| PUT    | `/api/v1/projects/{id}/collaborators/{user_id}` | Update collaborator role   |
| DELETE | `/api/v1/projects/{id}/collaborators/{user_id}` | Remove collaborator        |

### Job Endpoints

| Method | Endpoint                   | Description                 |
| :----- | :------------------------- | :-------------------------- |
| POST   | `/api/v1/jobs`             | Submit a code execution job |
| GET    | `/api/v1/jobs`             | List user's jobs            |
| GET    | `/api/v1/jobs/{id}`        | Get job status and result   |
| POST   | `/api/v1/jobs/{id}/cancel` | Cancel a running job        |

### Other Endpoints

| Method | Endpoint              | Description              |
| :----- | :-------------------- | :----------------------- |
| GET    | `/api/v1/health`      | Health check             |
| GET    | `/metrics`            | Prometheus-style metrics |
| GET    | `/api/v1/flags/{key}` | Get feature flag value   |
| POST   | `/api/v1/flags/{key}` | Set feature flag value   |

### WebSocket Endpoints

| Endpoint                         | Description                             |
| :------------------------------- | :-------------------------------------- |
| `/ws/{workspace_id}?token={jwt}` | Connect to workspace for real-time sync |

---

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run integration tests only
pytest tests/integration

# Run unit tests only
pytest tests/unit

# Run with coverage report
pytest --cov=app --cov-report=term-missing

# Run with verbose output
pytest -v
```

### Test Coverage

- **58 tests** covering authentication, projects, workspaces, collaborators, jobs, and WebSocket endpoints.
- **~59% code coverage** with focus on critical paths.

### Test Architecture

- **Unit Tests**: Test individual functions (password hashing, JWT tokens, permissions).
- **Integration Tests**: Test full API request/response cycles with mocked databases.
- Uses **SQLite in-memory** for fast integration tests without external dependencies.

---

## 🚢 Deployment Instructions

### Option 1: Vercel (Serverless)

1. **Connect Repository**: Link your GitHub repo to Vercel.

2. **Configure Framework**: Select **Other** or **FastAPI** as the framework preset.

3. **Set Environment Variables** in Vercel Dashboard:

   ```
   POSTGRES_URL=postgresql+asyncpg://user:pass@host:port/db
   MONGODB_URL=mongodb://user:pass@host:port
   MONGODB_DATABASE=your_db_name
   REDIS_URL=redis://user:pass@host:port
   SECRET_KEY=your-super-secret-key
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   REFRESH_TOKEN_EXPIRE_DAYS=7
   ```

4. **Override Install Command**:

   ```
   pip install -r requirements.txt
   ```

5. **Deploy**: Vercel will automatically deploy on push to `main`.

> **Note**: Vercel serverless functions have timeouts. For production WebSocket connections and Celery workers, use a persistent hosting platform.

### Option 2: Docker (Self-Hosted / VPS)

```bash
# Clone the repository
git clone https://github.com/your-username/collaborative-workspace.git
cd collaborative-workspace

# Build and run with Docker Compose
cd docker
docker-compose up -d --build

# View logs
docker-compose logs -f api
```

### Option 3: Railway

1. Create a new Railway project.
2. Add PostgreSQL, MongoDB, and Redis services.
3. Deploy the API from your GitHub repo.
4. Configure environment variables using Railway's dashboard.
5. Deploy the Celery worker as a separate service using `docker/Dockerfile.worker`.

### Environment Variables Reference

| Variable                      | Description                  | Default            |
| :---------------------------- | :--------------------------- | :----------------- |
| `POSTGRES_URL`                | PostgreSQL connection string | -                  |
| `MONGODB_URL`                 | MongoDB connection string    | -                  |
| `MONGODB_DATABASE`            | MongoDB database name        | `collab_workspace` |
| `REDIS_URL`                   | Redis connection string      | -                  |
| `CELERY_BROKER_URL`           | Celery broker (Redis) URL    | Same as REDIS_URL  |
| `CELERY_RESULT_BACKEND`       | Celery result backend URL    | Same as REDIS_URL  |
| `SECRET_KEY`                  | JWT signing secret           | -                  |
| `ALGORITHM`                   | JWT algorithm                | `HS256`            |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime        | `30`               |
| `REFRESH_TOKEN_EXPIRE_DAYS`   | Refresh token lifetime       | `7`                |
| `DEBUG`                       | Enable debug mode            | `false`            |

---

## 📂 Project Structure

```
app/
├── api/v1/           # Versioned API endpoints (auth, projects, jobs, etc.)
├── core/             # Security, permissions, rate limiting, metrics
├── models/           # SQLAlchemy (SQL) & Pydantic (NoSQL) models
├── schemas/          # Request/Response validation schemas
├── db/               # Database connection utilities (Postgres, Mongo, Redis)
├── services/         # Business logic services (feature flags)
├── websocket/        # Real-time collaboration (manager, handlers, pubsub)
└── workers/          # Celery task definitions

docker/
├── Dockerfile        # API container
├── Dockerfile.worker # Celery worker container
└── docker-compose.yml

tests/
├── unit/             # Unit tests for core functions
├── integration/      # API integration tests
└── conftest.py       # Shared test fixtures
```

---

## 📄 License

MIT
