# CSE 108 — Course Enrollment App

A full-stack course enrollment web application built with Flask, SQLite (Flask-SQLAlchemy), Flask-Admin, and a single-page HTML/CSS/JavaScript frontend.

## Features

- **Students:** View enrolled courses, browse available courses with live seat counts, and enroll in or drop courses.
- **Teachers:** View assigned courses, inspect class rosters, and enter or update student grades (`0–100`).
- **Admins:** Create, edit, and delete users, courses, and enrollments through the Flask-Admin dashboard at `/admin`.

## Project Structure

```text
CSE108-Group-Project/
├── app.py                  # Flask server, SQLAlchemy models, REST API, and Flask-Admin setup
├── requirements.txt        # Python dependencies
├── static/
│   ├── index.html          # Single-page frontend shell
│   ├── css/styles.css      # Application styles
│   └── js/
│       ├── app.js          # Frontend views and UI logic
│       ├── api.js          # Fetch client for /api/* endpoints
│       └── mock.js         # Optional standalone mock mode data
├── seed/
│   ├── seed.py             # Database seeder script
│   └── seed_data.csv       # Initial course, teacher, student, and grade data
└── instance/
    └── enrollment.db       # SQLite database (auto-created on seed or startup)
```

## Getting Started

### 1. Set Up the Environment

Create and activate a virtual environment, then install the dependencies:

```bash
python3 -m venv baseenv
source baseenv/bin/activate
pip install -r requirements.txt
```

On Windows (PowerShell):

```powershell
python -m venv baseenv
.\baseenv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Seed the Database

Populate `instance/enrollment.db` with the sample courses, teachers, students, and grades from `seed/seed_data.csv`:

```bash
python seed/seed.py
```

### 3. Run the Application

```bash
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

## Demo Accounts

All seeded accounts use the password **`password123`**.

| Role | Display Name | Username |
| :--- | :--- | :--- |
| Admin | Admin | `admin` |
| Teacher | Ralph Jenkins | `rjenkins` |
| Teacher | Susan Walker | `swalker` |
| Teacher | Ammon Hepworth | `ahepworth` |
| Teacher | Santosh Chandrasekhar | `schandrasekhar` |
| Student | Jose Santos | `jsantos` |
| Student | Betty Brown | `bbrown` |
| Student | John Stuart | `jstuart` |
| Student | Li Cheng | `lcheng` |
| Student | Nancy Little | `nlittle` |
| Student | Mindy Norris | `mnorris` |
| Student | Aditya Ranganath | `aranganath` |
| Student | Yi Wen Chen | `ychen` |
| Student | Nicholas Force | `nforce` |

## API Overview

| Method | Endpoint | Role | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/login` | Public | Sign in with `username` and `password` |
| `POST` | `/api/logout` | Any | Sign out of the current session |
| `GET` | `/api/me` | Any | Get the currently signed-in user |
| `GET` | `/api/courses` | Any | List all courses and enrollment counts |
| `GET` | `/api/student/courses` | Student | List courses the student is enrolled in |
| `POST` | `/api/student/courses/<id>` | Student | Enroll in a course |
| `DELETE` | `/api/student/courses/<id>` | Student | Drop a course |
| `GET` | `/api/teacher/courses` | Teacher | List courses taught by the teacher |
| `GET` | `/api/teacher/courses/<id>` | Teacher | View course details and student roster |
| `PUT` | `/api/teacher/courses/<id>/students/<sid>` | Teacher | Update a student's grade (`0–100` or `null`) |
| `GET` | `/admin` | Admin | Flask-Admin management interface |
