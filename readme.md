# CSE 108 — ACME University Enrollment App

Flask app for ACME University course enrollment. Students can view offered and enrolled courses, enroll and drop; teachers can review their rosters and edit grades; admins get CRUD access to users, courses, and enrollments through Flask-Admin.

## Project Structure

```text
CSE108-Group-Project/
├── app.py                # Flask app, SQLAlchemy models, views, enrollment/grade helpers
├── static/
│   ├── index.html        # Single-page app shell
│   ├── css/styles.css    # Responsive interface styles
│   └── js/               # Frontend, API client and optional mock data
├── seed/
│   ├── seed.py           # CSV seeder script and seed_db() helper
│   └── seed_data.csv     # Course, teacher, student, and grade workbook data
├── instance/
│   └── enrollment.db     # SQLite database (created/populated when running app.py or seed.py)
└── readme                # Project setup and usage documentation
```

---

## 1. Create and Activate the Python Environment

Create a virtual environment named `baseenv` from the repository root and install the required packages (`Flask` and `Flask-SQLAlchemy`, which also installs `SQLAlchemy` and `Werkzeug`):

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

> All commands below assume `baseenv` is activated (or can be run directly using `./baseenv/bin/python`).

---

## 2. Initialize or Seed the Database

### Option A: Seed the database with sample data (Recommended)

Run the seeder script from the project root (or from inside `seed/`):

```bash
python seed/seed.py
```

This executes `seed_db(reset=True)`, which:
1. Drops and recreates all tables in `instance/enrollment.db`.
2. Reads `seed/seed_data.csv` (carrying course fields forward per block, skipping blank separator rows, and trimming whitespace from names).
3. Creates the demo admin, teachers, students, courses, and enrollments with hashed passwords.

### Option B: Create empty tables only

If you want to initialize the database schema without inserting any seed data:

```bash
python app.py
```

This calls `init_db()`, which creates `users`, `courses`, and `enrollments` in `instance/enrollment.db` if they do not already exist.

---

Demo accounts use password **`password123`**. Seed data includes `admin`, teacher usernames such as `ahepworth`, and student usernames such as `mnorris`.

## 3. Run the Web App

Set a persistent secret key before deployment, then run the Flask server:

```bash
export FLASK_SECRET_KEY="use-a-long-random-value"
python app.py
```

Open `http://127.0.0.1:5000`. The browser interface uses the JSON endpoints in `app.py`; the admin dashboard is at `/admin` and requires an admin login. Teacher course names open their roster. Grades accept values from 0 to 100.

## 4. Database Functionality

### Database Models (`app.py`)

- **`User`** (`users` table)
  - Columns: `id`, `username` (unique), `password_hash`, `role` (`'student'`, `'teacher'`, or `'admin'`), `display_name`
  - Relationships: `courses_taught`, `enrollments`
  - Methods: `set_password(password)`, `check_password(password)`
  - Automatically trims surrounding whitespace from `username` and `display_name`.

- **`Course`** (`courses` table)
  - Columns: `id`, `name` (unique), `teacher_id`, `time`, `capacity` (`> 0`)
  - Relationships: `teacher`, `enrollments`
  - Derived properties (computed from `enrollments`):
    - `enrolled_count` (`int`)
    - `is_full` (`bool`)
    - `seats_remaining` (`int`)

- **`Enrollment`** (`enrollments` table)
  - Columns: `id`, `student_id`, `course_id`, `grade` (`float | None`)
  - Constraint: `UniqueConstraint("student_id", "course_id")` prevents duplicate enrollment in the same course and stores a course-specific grade per student.
  - Relationships: `student`, `course`

### Helper Functions

All database queries and mutations run inside `app.app_context()`:

```python
from app import Course, Enrollment, User, app, db, enroll_student, init_db, update_grade
from seed.seed import seed_db

# Initialize tables without clearing data
init_db()

# Re-seed without wiping existing records (updates grades / adds missing rows)
seed_db(reset=False)

# Or seed from a custom CSV file and reset tables first
# seed_db(csv_path="path/to/custom.csv", reset=True)

with app.app_context():
    # Look up a student and a course
    student = User.query.filter_by(username="jsantos").one()
    course = Course.query.filter_by(name="CS 106").one()

    # Verify a user's password
    valid = student.check_password("password123")

    # Check course availability
    print(f"{course.name}: {course.enrolled_count}/{course.capacity} (full={course.is_full})")

    # Enroll a student (rejects duplicates and full courses)
    ok, message = enroll_student(student.id, course.id)
    print(ok, message)

    # Update a student's grade in a specific course (other courses remain unchanged)
    ok, message = update_grade(student.id, course.id, 95.0)
    print(ok, message)
```

---

## 5. Seeded Data Reference

### Demo Accounts

All seeded accounts use the default password **`password123`** (stored as a Werkzeug password hash).

| Role | Display Name | Username | Password |
| :--- | :--- | :--- | :--- |
| Admin | Admin | `admin` | `password123` |
| Teacher | Ralph Jenkins | `rjenkins` | `password123` |
| Teacher | Susan Walker | `swalker` | `password123` |
| Teacher | Ammon Hepworth | `ahepworth` | `password123` |
| Teacher | Santosh Chandrasekhar | `schandrasekhar` | `password123` |
| Student | Jose Santos | `jsantos` | `password123` |
| Student | Betty Brown | `bbrown` | `password123` |
| Student | John Stuart | `jstuart` | `password123` |
| Student | Li Cheng | `lcheng` | `password123` |
| Student | Nancy Little | `nlittle` | `password123` |
| Student | Mindy Norris | `mnorris` | `password123` |
| Student | Aditya Ranganath | `aranganath` | `password123` |
| Student | Yi Wen Chen | `ychen` | `password123` |
| Student | Nicholas Force | `nforce` | `password123` |

### Seeded Courses

| Course | Teacher | Meeting Time | Enrolled / Capacity | Status |
| :--- | :--- | :--- | :--- | :--- |
| `Math 101` | Ralph Jenkins | `MWF 10:00-10:50 AM` | `4 / 8` | Open |
| `Physics 121` | Susan Walker | `TR 11:00-11:50 AM` | `5 / 10` | Open |
| `CS 106` | Ammon Hepworth | `MWF 2:00-2:50 PM` | `4 / 10` | Open |
| `CS 162` | Ammon Hepworth | `TR 3:00-3:50 PM` | `4 / 4` | Full |
| `CSE 120` | Santosh Chandrasekhar | `W 4:30-7:20 PM` | `1 / 120` | Open |
