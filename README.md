<p align="center">
  <img src="https://img.shields.io/badge/Next.js-14-black?style=for-the-badge&logo=next.js" alt="Next.js 14" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/PyTorch-2.x-EE4C2C?style=for-the-badge&logo=pytorch" alt="PyTorch" />
  <img src="https://img.shields.io/badge/Supabase-PostgreSQL-3FCF8E?style=for-the-badge&logo=supabase" alt="Supabase" />
  <img src="https://img.shields.io/badge/Vercel-Deploy-000?style=for-the-badge&logo=vercel" alt="Vercel" />
  <img src="https://img.shields.io/badge/Railway-Backend-0B0D0E?style=for-the-badge&logo=railway" alt="Railway" />
</p>

<h1 align="center">⚡ ClassPulse AI</h1>

<p align="center">
  <strong>AI-Powered Classroom Monitoring System</strong><br/>
  Real-time face recognition · Emotion detection · Engagement analytics · Smart attendance
</p>

---

## 🎯 What is ClassPulse AI?

ClassPulse AI transforms any classroom camera into an intelligent monitoring system. It uses computer vision and deep learning to:

- **Recognize students** in real-time using FaceNet512 face embeddings
- **Detect emotions** (attentive, confused, distracted, engaged, sleepy) with EfficientNetB3
- **Track engagement** across the entire classroom with per-student scoring
- **Automate attendance** with confidence-based face matching
- **Detect phone usage** using YOLOv8 object detection
- **Generate AI reports** with Claude for session summaries and insights

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Vercel (Frontend)                     │
│  Next.js 14 · Supabase Auth · Framer Motion · Recharts │
│  Edge Middleware · OG Images · Health Checks             │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS + WSS
┌────────────────────────┼────────────────────────────────┐
│               Railway (Python Backend)                   │
│  FastAPI · WebSocket Manager · Frame Processor           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │MediaPipe │ │FaceNet512│ │EfficientB3│ │ YOLOv8  │   │
│  │  Faces   │ │  Recog   │ │ Emotions  │ │ Phones  │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│  DeepSORT Tracker · Engagement Scorer · Report Gen      │
└────────────────────────┼────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
   ┌─────┴─────┐  ┌─────┴─────┐  ┌─────┴─────┐
   │ Supabase  │  │  Upstash  │  │  Railway   │
   │PostgreSQL │  │   Redis   │  │  Volume    │
   │ + pgvector│  │ (cache)   │  │ (models)   │
   └───────────┘  └───────────┘  └───────────┘
```

---

## 📂 Project Structure

```
ClassPulseAI/
├── frontend/                    # Next.js 14 application
│   ├── app/
│   │   ├── (auth)/login/        # Authentication page (Email + Google OAuth)
│   │   ├── (dashboard)/         # Protected dashboard routes
│   │   │   ├── dashboard/       # Main overview with KPI cards
│   │   │   ├── live/            # Real-time video stream + detection overlay
│   │   │   ├── attendance/      # Attendance tracking
│   │   │   ├── analytics/       # Engagement charts & trends
│   │   │   ├── reports/         # AI-generated session reports
│   │   │   ├── students/        # Student management
│   │   │   └── settings/        # System configuration
│   │   └── api/
│   │       ├── health/          # Service health check endpoint
│   │       ├── og/              # Dynamic OG image generation
│   │       └── reports/generate/ # Report generation proxy
│   ├── components/              # Reusable UI components
│   ├── lib/                     # Supabase client, Redis, WebSocket, utils
│   ├── middleware.ts            # Edge auth protection
│   ├── vercel.json              # Vercel deployment config
│   └── next.config.ts           # Next.js configuration
│
├── backend/                     # FastAPI Python backend
│   ├── main.py                  # App entry point + WebSocket endpoint
│   ├── config.py                # Pydantic settings (env-based config)
│   ├── websocket_manager.py     # Connection manager with rooms + heartbeat
│   ├── services/
│   │   ├── camera_service.py    # OpenCV capture (4K → 1080p)
│   │   ├── face_detection.py    # MediaPipe face detection
│   │   ├── face_recognition.py  # DeepFace FaceNet512 matching
│   │   ├── emotion_detection.py # EfficientNetB3 emotion classifier
│   │   ├── phone_detection.py   # YOLOv8 phone detection
│   │   ├── tracking_service.py  # DeepSORT multi-object tracker
│   │   ├── engagement_scorer.py # Weighted engagement scoring
│   │   ├── analytics_service.py # Historical analytics queries
│   │   ├── report_generator.py  # Claude-powered report generation
│   │   └── redis_service.py     # Redis caching layer
│   ├── models/
│   │   ├── emotion_model.py     # Production emotion inference wrapper
│   │   ├── face_model.py        # Production face recognition wrapper
│   │   └── schemas.py           # Pydantic response schemas
│   ├── training/
│   │   ├── train_emotion_model.py       # EfficientNetB3 training pipeline
│   │   ├── setup_face_recognition.py    # FaceNet512 embedding generator
│   │   └── validate_models.py          # Model validation + benchmarks
│   ├── routers/                 # FastAPI route modules
│   ├── utils/                   # Frame processor, GPU accelerator, logger
│   ├── railway.toml             # Railway deployment config
│   ├── Procfile                 # Render deployment alternative
│   └── requirements.txt         # Python dependencies
│
├── database/
│   ├── schema.sql               # Full PostgreSQL schema (pgvector, RLS)
│   └── seed.sql                 # Sample data
│
├── .github/workflows/
│   └── deploy.yml               # CI/CD: lint → build → deploy
│
├── docker-compose.yml           # Local development stack
└── .gitignore                   # Secrets, models, builds excluded
```

---

## 🚀 Quick Start

### Prerequisites

- **Node.js** ≥ 20
- **Python** ≥ 3.11
- **Supabase** project (free tier works)
- **Redis** (local or Upstash for production)

### 1. Clone the repository

```bash
git clone https://github.com/ashurajs552-droid/ClassPulseAI.git
cd ClassPulseAI
```

### 2. Frontend setup

```bash
cd frontend
npm install

# Configure environment
cp .env.production .env.local
# Edit .env.local with your Supabase credentials

npm run dev
# → http://localhost:3000
```

### 3. Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

python main.py
# → http://localhost:8000
```

### 4. Database setup

Run `database/schema.sql` in your Supabase SQL Editor to create all tables with RLS policies.

---

## 🧠 AI Models

| Model | Architecture | Task | Target |
|-------|-------------|------|--------|
| **Emotion Detection** | EfficientNetB3 (transfer learning) | Classify: attentive, confused, distracted, engaged, sleepy | ≥ 90% accuracy, ≤ 15ms/face |
| **Face Recognition** | FaceNet512 (InceptionResnetV1) | Student identification via 512-d embeddings | ≥ 90% accuracy, ≤ 50ms/face |
| **Phone Detection** | YOLOv8x | Detect phone usage in classroom | ≥ 72% confidence threshold |
| **Face Detection** | MediaPipe | Locate all faces in frame | ≥ 70% confidence, 60+ faces |
| **Tracking** | DeepSORT | Multi-object identity persistence | 30-frame max age |

### Training

```bash
cd backend

# Train emotion model (requires FER2013/AffectNet dataset)
python -m training.train_emotion_model --data_dir ./data/emotions --epochs 50

# Generate face embeddings (requires student photos)
python -m training.setup_face_recognition --photos_dir ./data/students

# Validate everything
python -m training.validate_models --benchmark_faces 60
```

---

## ☁️ Deployment

### Frontend → Vercel

1. Import the repo on [vercel.com](https://vercel.com)
2. Set **Root Directory** to `frontend`
3. Add environment variables in the Vercel dashboard:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_API_URL` (Railway backend URL)
   - `NEXT_PUBLIC_WS_URL` (Railway WSS URL)
   - `UPSTASH_REDIS_REST_URL`
   - `UPSTASH_REDIS_REST_TOKEN`

### Backend → Railway

1. Create a new project on [railway.app](https://railway.app)
2. Link the `backend/` directory
3. Add a persistent volume mounted at `/app/models`
4. Set environment variables:
   - `ENVIRONMENT=production`
   - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
   - `REDIS_URL` (or Upstash credentials)
   - `ANTHROPIC_API_KEY`
   - `FRONTEND_URL=https://classpulse-ai.vercel.app`

### CI/CD

The GitHub Actions workflow (`.github/workflows/deploy.yml`) automatically:
1. **Tests** — Lint + type-check + build (frontend), flake8 + pytest (backend)
2. **Deploys** — On push to `main`, deploys to Vercel and Railway

Set these GitHub Secrets:
- `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`
- `RAILWAY_TOKEN`

---

## 🔐 Security

- **Edge Middleware** — All dashboard routes require Supabase session cookies
- **Row Level Security** — Every database table has RLS policies
- **CORS** — Production origins whitelist (auto-detects Vercel preview URLs)
- **Secrets** — All credentials via environment variables, never committed
- **pgvector** — Face embeddings stored securely in Supabase with vector indexing

---

## 📊 Real-Time Features

| Feature | Technology | Update Rate |
|---------|-----------|-------------|
| Video stream | WebSocket + Canvas rendering | 15 FPS |
| Face detection | MediaPipe | Every frame |
| Emotion classification | EfficientNetB3 + temporal smoothing | Every frame |
| Attendance updates | FaceNet512 cosine similarity | Every 30 frames |
| Engagement metrics | Weighted scoring engine | Every 2 seconds |
| Alert notifications | WebSocket broadcast | Real-time |
| Session metrics | Upstash Redis cache (5s TTL) | Every 5 seconds |

---

## 🛠️ Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | Next.js 14, TypeScript, Framer Motion, Recharts, Supabase SSR |
| **Backend** | FastAPI, Python 3.11, WebSockets, Uvicorn |
| **AI/ML** | PyTorch, EfficientNetB3, FaceNet512, MediaPipe, YOLOv8, DeepSORT |
| **Database** | Supabase (PostgreSQL + pgvector + Realtime + Auth) |
| **Cache** | Upstash Redis (serverless) / Redis |
| **Deploy** | Vercel (frontend), Railway (backend), GitHub Actions (CI/CD) |
| **Design** | Dark AI theme, glassmorphism, gradient text, Inter font |

---

## 📝 License

This project is for educational and research purposes.

---

<p align="center">
  Built with ⚡ by <a href="https://github.com/ashurajs552-droid">Ashu Raj S</a>
</p>
