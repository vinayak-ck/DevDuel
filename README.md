<div align="center">

# ⚔️ DevDuel

### Real-time 1v1 Competitive Coding Platform

*Battle other developers. Solve DSA problems faster. Climb the leaderboard.*

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.x-092E20?style=flat&logo=django&logoColor=white)](https://djangoproject.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Redis](https://img.shields.io/badge/Redis-7.x-DC382D?style=flat&logo=redis&logoColor=white)](https://redis.io)
[![WebSocket](https://img.shields.io/badge/WebSocket-Django_Channels-7F77DD?style=flat)](https://channels.readthedocs.io)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

[Live Demo](#) · [Report Bug](https://github.com/vinayak-ck/DevDuel/issues) · [Request Feature](https://github.com/vinayak-ck/DevDuel/issues)

</div>

---

## 📖 What is DevDuel?

DevDuel is a **real-time 1v1 competitive coding platform** where two developers battle each other to solve a DSA problem first. Think LeetCode, but with a live opponent, a ticking timer, and an ELO-based ranking system.

Players connect to a battle room via WebSocket. Both see the same problem. The first to get **Accepted (AC)** wins. Their ELO ratings update instantly. The leaderboard reflects in real-time.

Built as a portfolio project to demonstrate full-stack engineering depth — from real-time WebSocket architecture to sandboxed code execution to a live ELO ranking system.

---

## ✨ Features

| Feature | Description |
|---|---|
| ⚡ **Real-time battles** | WebSocket-powered — see opponent's progress live as they type |
| 🖥️ **Monaco Editor** | VS Code's editor embedded in the browser — Python, C++, Java |
| ⚖️ **ELO rating system** | Chess-style ranking — fair matchmaking, meaningful progression |
| 🔒 **Sandboxed judge** | User code runs in isolated subprocesses with time + memory limits |
| 🏆 **Live leaderboard** | Redis Sorted Set — updates the instant a battle ends |
| 📊 **Rating history** | Track your ELO progression over time with a chart |
| 🔀 **Matchmaking** | Auto-match you with an opponent of similar rating |
| 🏷️ **Problem tags** | Filter problems by topic — DP, Graphs, Two Pointers, etc. |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        Browser                          │
│  Monaco Editor + BattleSocket JS + Progress Bar UI      │
└──────────────┬──────────────────────────────────────────┘
               │ WebSocket (ws://)  +  HTTP (REST)
               ▼
┌─────────────────────────────────────────────────────────┐
│              Django + Channels (port 8000)               │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────────┐  │
│  │  REST APIs  │  │  Consumers  │  │  Django Admin  │  │
│  │  (views.py) │  │(consumers.py│  │  (problems,    │  │
│  │  auth, user │  │ battle room)│  │   test cases)  │  │
│  └─────────────┘  └──────┬──────┘  └────────────────┘  │
└─────────────────────────────┼───────────────────────────┘
               ┌──────────────┼──────────────┐
               ▼              ▼              ▼
    ┌──────────────┐  ┌────────────┐  ┌──────────────┐
    │    Redis     │  │   MySQL    │  │   FastAPI    │
    │  Channel     │  │            │  │    Judge     │
    │  layer +     │  │  Problems  │  │  (port 8001) │
    │  Leaderboard │  │  Battles   │  │              │
    │  Cache       │  │  Ratings   │  │  Sandboxed   │
    └──────────────┘  └────────────┘  │  subprocess  │
                                      └──────────────┘
```

### Service breakdown

| Service | Tech | Port | Responsibility |
|---|---|---|---|
| Main app | Django + Channels | 8000 | Auth, REST APIs, WebSocket consumers |
| ASGI server | Daphne | 8000 | Serves HTTP + WebSocket simultaneously |
| Judge | FastAPI + Uvicorn | 8001 | Sandboxed code execution, verdict |
| Channel layer | Redis | 6379 | WS broadcast between Django workers |
| Database | MySQL | 3306 | All persistent data |

---

## 🗂️ Project Structure

```
devduel/
│
├── django_app/                   # Main Django application
│   ├── devduel/                  # Django project settings
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── asgi.py               # ASGI config (HTTP + WebSocket)
│   │   └── wsgi.py
│   │
│   ├── battle/                   # Battle room app
│   │   ├── models.py             # Battle, Submission, RatingHistory
│   │   ├── consumers.py          # WebSocket consumer (BattleConsumer)
│   │   ├── routing.py            # WebSocket URL patterns
│   │   ├── views.py              # REST API endpoints
│   │   ├── serializers.py        # DRF serializers
│   │   ├── services.py           # ELO calculation, battle logic
│   │   └── admin.py
│   │
│   ├── users/                    # User profiles, auth
│   │   ├── models.py             # UserProfile
│   │   ├── views.py              # Register, login, profile
│   │   └── admin.py
│   │
│   ├── problems/                 # Problem management
│   │   ├── models.py             # Problem, TestCase, Tag
│   │   ├── views.py              # Problem list, detail
│   │   └── admin.py
│   │
│   └── elo/                      # ELO algorithm module
│       └── calculator.py         # calculate_elo(), expected_score()
│
├── judge/                        # FastAPI code execution service
│   ├── main.py                   # FastAPI app, /execute endpoint
│   ├── sandbox.py                # Subprocess sandboxing, resource limits
│   └── requirements.txt
│
├── frontend/                     # Static frontend assets
│   ├── static/
│   │   ├── css/
│   │   │   ├── base.css
│   │   │   ├── battle.css        # Battle room styles
│   │   │   └── leaderboard.css
│   │   └── js/
│   │       ├── battle-socket.js  # BattleSocket class (WS client)
│   │       └── battle-room.js    # Monaco + battle UI logic
│   └── templates/
│       ├── base.html
│       ├── battle/
│       │   ├── room.html         # The battle page
│       │   └── lobby.html        # Find/create battles
│       ├── problems/
│       │   ├── list.html
│       │   └── detail.html
│       └── users/
│           ├── profile.html
│           └── leaderboard.html
│
├── docs/                         # Architecture docs, diagrams
│   └── architecture.md
│
├── .env.example                  # Environment variables template
├── .gitignore
├── requirements.txt              # Django app dependencies
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- MySQL 8+
- Redis 7+
- g++ (for C++ judging) — `sudo apt install g++`

### 1. Clone the repository

```bash
git clone https://github.com/vinayak-ck/DevDuel.git
cd devduel
```

### 2. Set up the virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Linux / Mac
# venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
# edit .env with your MySQL credentials, SECRET_KEY, etc.
```

### 5. Set up the database

```bash
# create the MySQL database
mysql -u root -p -e "CREATE DATABASE devduel CHARACTER SET utf8mb4;"

# run migrations
cd django_app
python manage.py migrate

# create a superuser (for Django admin)
python manage.py createsuperuser
```

### 6. Start Redis

```bash
sudo service redis-server start
redis-cli ping   # should return PONG
```

### 7. Start the services

```bash
# terminal 1 — Django + Channels (main app)
cd django_app
python manage.py runserver

# terminal 2 — FastAPI judge
cd judge
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### 8. Open the app

```
Main app:   http://localhost:8000
Judge API:  http://localhost:8001/docs   (interactive API docs)
Admin:      http://localhost:8000/admin
```

---

## 🎮 How a Battle Works

```
1. Player A clicks "Find Battle" → matchmaking checks for open rooms
2. If no match → Player A's room goes into the lobby (status: waiting)
3. Player B joins → both connected via WebSocket → battle starts
4. Both see the same problem in Monaco Editor
5. Players write code → line count sent to opponent's progress bar every 300ms
6. Player clicks Submit → code sent to FastAPI judge via Django Consumer
7. Judge runs code in sandboxed subprocess → returns AC / WA / TLE / RE
8. Verdict broadcast to both players via Redis Pub/Sub → Django Channels → WebSocket
9. First AC → battle over → ELO updates → leaderboard refreshes
```

---

## 🧠 Technical Highlights

### Real-time with Django Channels + Redis

WebSocket connections are managed by `BattleConsumer`. Redis acts as the channel layer — when Player A submits code on Worker 1, the verdict is published to Redis and delivered to Player B on Worker 2 via `group_send`.

### Sandboxed Code Execution

User code runs in isolated subprocesses via FastAPI. Resource limits enforced with Python's `resource` module:
- **Time limit** — `subprocess.TimeoutExpired` after N seconds
- **Memory limit** — `RLIMIT_AS` caps address space
- **Process limit** — `RLIMIT_NPROC` defeats fork bombs
- **File size limit** — `RLIMIT_FSIZE` prevents disk attacks

### ELO Rating System

Implemented from scratch using Arpad Elo's formula:

```
E_A = 1 / (1 + 10^((R_B - R_A) / 400))
R'_A = R_A + K × (S_A - E_A)
```

Dynamic K-factor: K=64 (provisional, <20 battles), K=32 (standard), K=16 (rated 2000+).

### Leaderboard with Redis Sorted Set

Ratings stored in Redis `ZADD leaderboard score username`. Top-N queries via `ZRANGE leaderboard 0 9 REV WITHSCORES` — O(log N), sub-millisecond even at millions of users.

---

## 🗄️ Database Schema

8 core tables:

```
auth_user          — Django built-in
user_profile       — ELO, wins, losses, streak
problem            — title, description, difficulty, time/memory limits
test_case          — input/output pairs per problem
battle             — room_id, players, problem, status, timestamps
submission         — code, language, verdict, time_ms per submission
rating_history     — immutable ELO change log (event sourcing)
tag                — problem categories (DP, Graphs, etc.)
```

---

## 🧪 Verdict types

| Verdict | Meaning | Cause |
|---|---|---|
| **AC** | Accepted | All test cases passed |
| **WA** | Wrong Answer | Output doesn't match expected |
| **TLE** | Time Limit Exceeded | Exceeded time limit |
| **RE** | Runtime Error | Crash, exception, segfault, OOM |
| **CE** | Compile Error | C++/Java failed to compile |

---

<!--
## 🛣️ Roadmap

- [x] Project setup and architecture
- [ ] Django models and migrations
- [ ] Django Channels battle room
- [ ] Monaco Editor frontend
- [ ] FastAPI judge with sandboxing
- [ ] ELO system and leaderboard
- [ ] User auth and profiles
- [ ] Matchmaking queue
- [ ] Problem admin panel
- [ ] Rating chart (history visualization)
- [ ] Docker compose for deployment
- [ ] Nginx reverse proxy setup

---
-->

## 🤝 Contributing

This is a portfolio project but contributions are welcome.

```bash
git checkout -b feature/your-feature-name
git commit -m "feat: add your feature"
git push origin feature/your-feature-name
# open a pull request
```

---

## 👨‍💻 Author

**Vinayak C Kanavalli**

[![GitHub](https://img.shields.io/badge/GitHub-vinayak--ck-181717?style=flat&logo=github)](https://github.com/vinayak-ck)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?style=flat&logo=linkedin)](https://www.linkedin.com/in/vinayak-c-kanavalli-/)
[![Portfolio](https://img.shields.io/badge/Portfolio-vinayak--ck.github.io-4F46E5?style=flat)](https://vinayak-ck.github.io/MyPortfolio/)
[![LeetCode](https://img.shields.io/badge/LeetCode-250%2B_solved-FFA116?style=flat&logo=leetcode)](https://leetcode.com/u/vinayak_c_kanavalli/)

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
  <sub>Built with ❤️ by Vinayak — one battle at a time.</sub>
</div>

