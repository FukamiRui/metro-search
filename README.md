# 🚇 NYC Subway Search API
[![CI Pipeline](https://github.com/FukamiRui/metro-search/actions/workflows/python-app.yml/badge.svg)](https://github.com/FukamiRui/metro-search/actions/workflows/ci.yml)
![Coverage](https://img.shields.io/badge/coverage-87%25-brightgreen)


A high-performance subway route search application using GTFS (General Transit Feed Specification) data for the New York City Metro system. Built with **FastAPI**, **SQLAlchemy**, and **Sliding Window / Binary Search algorithms**.

---

## 🌐 Live Demo

* **URL:** [https://metro-search-portfolio.vercel.app/](https://metro-search-portfolio.vercel.app/)
> Hosted on Vercel (Python serverless function).

---

## ⚡ Key Features

* **O(log N) Direct Route Search:** 
 - Fast binary search ("bisect") implementation for station departures over GTFS schedule data.
* **BFS Transfer Route Search:** 
 - Multi-leg transfer route finding constrained to maximum 3-step search depth to maintain minimal runtime latency.
* **Haversine Nearest Station Calculation:** 
 - Real-time spatial query calculating closest subway stops from user coordinates ($O(N)$ space / time efficiency).
* **Robust Error Handling:** 
 - Custom exception handling ensuring high availability and zero unhandled server crashes (500 errors).

---

## 🛠 Tech Stack

|       Category         |            Technologies                 |
|    --------------      |        --------------------             |
| **Language**           | Python 3.14                             |
| **Backend Framework**  | FastAPI, Uvicorn, Gunicorn              |
| **Database & ORM**     | PostgreSQL, SQLite, SQLAlchemy (ORM)    |
| **Frontend**           | HTML5, CSS3, JavaScript                 |
| **Testing & Quality**  | Pytest (Unit & Integration), Pytest-Cov |
| **DevOps & CI/CD**     | Docker, Docker Compose, GitHub Actions  |

---
## Dataset

This application processes NYC Subway GTFS data:

- 563,000+ stop-time schedule records
- 20,000+ trip records
- 1,400+ station records
- 30 subway routes

The data is imported into PostgreSQL and accessed through SQLAlchemy ORM with optimized queries.
---

## 🚀 Performance Optimization & Complexity

| Algorithm / Feature | Time Complexity | Space Complexity | Optimization Strategy |
| :--- | :--- | :--- | :--- |
| **Direct Route Search** | O(log N + M) | O(M) | Binary search (bisect_left) on cached departure times |
| **Transfer Search (BFS)** | O(V + E) | O(V) | BFS with visited-state pruning and maximum transfer depth |
| **Nearest Station** | O(N) | O(1) | Haversine distance over cached station coordinates |

---

## 🧪 Testing & Continuous Integration (CI)

* **Code Coverage:** **87%** 
 - (Excluding non-core data migration scripts via `.coveragerc`)
* **Automated CI Pipeline:** 
 - GitHub Actions automatically runs `pytest` and coverage checks on every Push and Pull Request.

```text
        Stmts   Miss  Cover
---------------------------
TOTAL    530     66    88%

.
--- 
```
## 📂 Project Structure

```plaintext
├── .github/
│   └── workflows/
│       └── python-app.yml  # GitHub Actions CI Workflow
├── data/
│   └── gtfs/
│       ├── routes.txt
│       ├── stops.txt
│       ├── trips.txt
│       └── stop_times.txt
├── models.py               # SQLAlchemy DB Models
├── database.py             # Database Connection & Session Management
├── main.py                 # FastAPI entry point: /search_route, /check_stations, calculate_nearest_station
├── search.py               # Core algorithms: direct search (binary search), transfer search (depth-bounded BFS), nearest station (Haversine)
├── test_api.py             # Pytest Test Cases
├── .coveragerc             # Coverage Exclusions Configuration
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
└── requirements.txt
```

---

## 🏗️ Architecture

<details>
<summary><strong>System Architecture</strong></summary>

```text

[ Client / User Request ]
         │
         ▼
 ┌─────────────────────────────────────────────────────────┐
 │                   FastAPI Application                   │
 │                        (main.py)                        │
 └────────────────────────────┬────────────────────────────┘
                              │
          ┌───────────────────┴───────────────────┐
          │ Lifecycle Startup Cache (In-Memory)  │
          │  - stop_name_to_ids                   │
          │  - stations_spatial_data              │
          └───────────────────┬───────────────────┘
                              │
                  Is GPS / Nearest Request?
                   ├── YES ──> [ calculate_nearest_station() ]
                   │              └─ Haversine distance calculation
                   ▼
       [ /search_route Endpoint ]
                  │
        ┌─────────┴─────────────────────────┐
        │                                   │
        ▼                                   ▼
 [ search_direct_db() ]            [ search_transfer_db() ]
   (search.py)                       (search.py)
        │                                   │
        │  SQLAlchemy ORM (Session)         │  SQLAlchemy ORM (Session)
        │  Execution                        │  Execution
        ▼                                   ▼
 ┌─────────────────────────────────────────────────────────┐
 │                    SQL Database                         │
 │        (PostgreSQL / SQLite via models.py)              │
 │                                                         │
 │  • t_board JOIN t_alight JOIN trip (Direct)             │
 │  • 1st Leg Query  ──> FETCH Limit 1000                  │
 │  • 2nd Leg Query  ──> STREAM yield_per 5000             │
 └────────────────────────────┬────────────────────────────┘
                              │
                              │ Query Results Returned
                              ▼
            [ Merge & Deduplicate (FastAPI / search.py) ]
            - In-memory Hash Join (1st Leg Arrival <= 2nd Leg Departure)
            - Deduplicate by (dep_time, route_id)
            - Sort chronologically
                              │
                              ▼
               [ JSON Response Output ]

```
</details>
--- 

## 🛠 Installation & Local Setup

### 1. Clone the repository
```bash
git clone https://github.com/FukamiRui/metro-search.git
cd metro-search
```

### 2. Create Environment Variables
Create a .env file in the project root directory.
You can copy the example configuration:
```bash
cp .env.example .env
```

Update the values in .env:
```env
# PostgreSQL Configuration
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=mta_subway_db

# SQLAlchemy Database URL
DATABASE_URL=postgresql://your_user:your_password@db:5432/mta_subway_db
```

Note: Replace the placeholder values with your own local database credentials.
Do not commit the .env file or expose database credentials publicly.

### 3. Run the Application with Docker Compose
```bash
docker compose up --build
```

The API will be available at:
http://localhost:8000

Swagger API documentation:
http://localhost:8000/docs

### 4. Run Tests
```bash
docker compose exec app pytest
```

---

## Trade-off
I chose PostgreSQL over an in-memory data store.

The benchmark below measures the time and memory required to load the entire dataset into the application.

Although an in-memory database can provide faster lookups after loading, it requires loading all data into memory first. For this project, PostgreSQL achieved much faster data loading and significantly lower memory usage, so I prioritized startup performance and memory efficiency over the potential benefit of faster in-memory searches.

#### Benchmark (Loading the entire dataset)

**In-memory database**

- Execution time: 205.96 s
- Peak memory usage: 381.87 MB

**PostgreSQL**

- Execution time: 0.79 s
- Peak memory usage: 3.03 MB

---

## 🔮 Future Improvements
GTFS-Realtime Integration: Fetch live delay and service disruption feeds via MTA APIs.
Redis Caching Layer: Implement Redis to cache frequent search results and reduce database load.
Map UI Enhancement: Interactive map visualization using Leaflet.js / Mapbox.