# How the front end talks to the server

The front end (everything in `static/`) gets its data by calling web addresses on the Flask
server, like `/api/login`. This file lists the addresses it calls right now and the replies it
expects, so the pieces can fit together. None of it is set in stone. If something here doesn't
fit how the backend is being built, let me know and I can change the front end to match.

Every address starts with `/api/`, and the front end expects JSON replies.

---

## How the page gets loaded

The front end is plain HTML, CSS and JavaScript in the `static/` folder. It loads its files with
relative paths (`css/...`, `js/...`), so if Flask serves it, this setup works:

```python
app = Flask(__name__, static_folder="static", static_url_path="")

@app.route("/")
def index():
    return app.send_static_file("index.html")
```

With Flask's default static settings, the page would load without its styling and code.

---

## What the front end expects back

### A user
```json
{ "id": 15, "username": "mnorris", "role": "student", "display_name": "Mindy Norris" }
```
`role` is `"student"`, `"teacher"`, or `"admin"`.

### A course
```json
{ "id": 4, "name": "CS 162", "teacher": "Ammon Hepworth",
  "time": "TR 3:00-3:50 PM", "enrolled": 4, "capacity": 4 }
```
`teacher` is shown as the teacher's name, and `enrolled` is the number of students in the course.

### Errors
When something goes wrong, the front end shows whatever is in `error` to the user:
```json
{ "error": "CS 162 is full" }
```
It looks at the status code to decide what to do:

| Code | What the front end does |
|---|---|
| 401 | Sends the user back to the login page (or shows "Invalid username or password" on login) |
| 403 / 404 | Shows the message; on a course page, goes back to the course list |
| 400 / 409 / others | Shows the message |

---

## Login

| When the user… | The front end calls | It sends | It expects back |
|---|---|---|---|
| clicks Sign in | `POST /api/login` | `{"username": "...", "password": "..."}` | the user, or a 401 if the login is wrong |
| clicks Sign out | `POST /api/logout` | nothing | anything with a 200 status |
| opens or reloads the page | `GET /api/me` | nothing | the logged-in user, or a 401 if nobody is logged in |

If the logged-in user is an admin, the front end sends them to `/admin`.

---

## Student pages

| When the student… | The front end calls | It expects back |
|---|---|---|
| opens "Your Courses" | `GET /api/student/courses` | a list of the courses they're in |
| opens "Add Courses" | `GET /api/courses` | a list of all courses, each with `"is_enrolled": true/false` |
| clicks Add | `POST /api/student/courses/<course_id>` | the course, or an error if they can't join it (full, already enrolled) |
| clicks Drop | `DELETE /api/student/courses/<course_id>` | the course, or an error |

The "Full" and "Enrolled" labels on the page come from `enrolled`, `capacity`, and `is_enrolled`.

---

## Teacher pages

| When the teacher… | The front end calls | It sends | It expects back |
|---|---|---|---|
| opens "Your Courses" | `GET /api/teacher/courses` | nothing | a list of the courses they teach |
| clicks a course | `GET /api/teacher/courses/<course_id>` | nothing | the course and its students (below) |
| saves a grade | `PUT /api/teacher/courses/<course_id>/students/<student_id>` | `{"grade": 92.5}` | `{"student_id": 16, "course_id": 4, "grade": 92.5}` |

Clicking a course expects this shape:
```json
{
  "course": { "id": 4, "name": "CS 162", "teacher": "Ammon Hepworth",
              "time": "TR 3:00-3:50 PM", "enrolled": 4, "capacity": 4 },
  "students": [
    { "student_id": 16, "name": "Aditya Ranganath", "grade": 99 },
    { "student_id": 14, "name": "Nancy Little", "grade": 87 }
  ]
}
```
A grade can be a decimal, or `null` if there isn't one yet. A blank grade box sends `null`.

---

## Seeing how it behaves

Open `static/index.html` directly in a browser. It runs on built-in sample data that matches the
database readme ("mock mode", shown by a yellow banner), so you can click through every page
without the server. Log in with `mnorris` or `ahepworth`, password `password123`.
