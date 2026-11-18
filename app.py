from typing import Optional

import os
from flask import Flask, jsonify, redirect, request, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.menu import MenuLink
from flask_admin.contrib.sqla import ModelView
from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__, static_url_path="")
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///enrollment.db"

db = SQLAlchemy(app)


def current_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


class User(db.Model):
    """Application user account for students, teachers, and admins."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('student', 'teacher', 'admin')",
            name="ck_user_role",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)

    courses_taught: Mapped[list["Course"]] = relationship(
        "Course",
        back_populates="teacher",
        cascade="all, delete-orphan",
    )
    enrollments: Mapped[list["Enrollment"]] = relationship(
        "Enrollment",
        back_populates="student",
        cascade="all, delete-orphan",
    )

    @validates("username", "display_name")
    def _strip_text(self, key: str, value: str) -> str:
        """Trim surrounding whitespace when storing usernames or display names."""
        return value.strip() if isinstance(value, str) else value

    def set_password(self, password: str) -> None:
        """Hash and store the user's password."""
        if self.display_name:
            self.display_name = self.display_name.strip()
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify a plaintext password against the stored password hash."""
        return check_password_hash(self.password_hash, password)

    def __str__(self) -> str:
        return self.display_name

    def __repr__(self) -> str:
        return f"<User {self.username!r} role={self.role!r}>"


class Course(db.Model):
    """Course offering taught by a teacher with a fixed seat capacity."""

    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="ck_course_capacity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    time: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    teacher: Mapped["User"] = relationship(
        "User",
        back_populates="courses_taught",
    )
    enrollments: Mapped[list["Enrollment"]] = relationship(
        "Enrollment",
        back_populates="course",
        cascade="all, delete-orphan",
    )

    @validates("name", "time")
    def _strip_text(self, key: str, value: str) -> str:
        """Trim surrounding whitespace on course name and meeting time."""
        return value.strip() if isinstance(value, str) else value

    @property
    def enrolled_count(self) -> int:
        """Derive current enrollment count from enrollment rows."""
        return len(self.enrollments)

    @property
    def is_full(self) -> bool:
        """Return True when the course has reached or exceeded capacity."""
        return self.enrolled_count >= self.capacity

    @property
    def seats_remaining(self) -> int:
        """Return the number of open seats remaining in the course."""
        return max(0, self.capacity - self.enrolled_count)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Course {self.name!r} ({self.enrolled_count}/{self.capacity})>"


class Enrollment(db.Model):
    """Association model linking a student to a course with a course-specific grade."""

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_student_course"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False)
    grade: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    student: Mapped["User"] = relationship(
        "User",
        back_populates="enrollments",
    )
    course: Mapped["Course"] = relationship(
        "Course",
        back_populates="enrollments",
    )

    def __str__(self) -> str:
        return f"{self.student} - {self.course}"

    def __repr__(self) -> str:
        return (
            f"<Enrollment student_id={self.student_id} "
            f"course_id={self.course_id} grade={self.grade!r}>"
        )


def enroll_student(student_id: int, course_id: int) -> tuple[bool, str]:
    """Enroll a student in a course if not already enrolled and seats remain."""
    student = db.session.get(User, student_id)
    if student is None or student.role != "student":
        return False, "Student not found."

    course = db.session.get(Course, course_id)
    if course is None:
        return False, "Course not found."

    existing = Enrollment.query.filter_by(
        student_id=student_id,
        course_id=course_id,
    ).first()
    if existing is not None:
        return False, "Student is already enrolled in this course."

    if course.is_full:
        return False, "Course is full."

    enrollment = Enrollment(student_id=student_id, course_id=course_id)
    db.session.add(enrollment)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return False, "Could not enroll student due to a database constraint."

    return True, "Enrolled successfully."


def update_grade(
    student_id: int,
    course_id: int,
    grade: Optional[float],
) -> tuple[bool, str]:
    """Update a student's grade for a single course enrollment."""
    enrollment = Enrollment.query.filter_by(
        student_id=student_id,
        course_id=course_id,
    ).first()
    if enrollment is None:
        return False, "Enrollment record not found."

    enrollment.grade = grade
    db.session.commit()
    return True, "Grade updated successfully."


def init_db() -> None:
    """Create all database tables within the Flask application context."""
    with app.app_context():
        db.create_all()


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


def api_error(message: str, status: int):
    return jsonify(error=message), status


def api_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "display_name": user.display_name,
    }


def api_course(course: Course, student_id: Optional[int] = None) -> dict:
    data = {
        "id": course.id,
        "name": course.name,
        "teacher": course.teacher.display_name,
        "time": course.time,
        "enrolled": course.enrolled_count,
        "capacity": course.capacity,
    }
    if student_id is not None:
        data["is_enrolled"] = Enrollment.query.filter_by(
            student_id=student_id,
            course_id=course.id,
        ).first() is not None
    return data


def require_api_role(role: Optional[str] = None):
    user = current_user()
    if user is None:
        return None, api_error("Not logged in", 401)
    if role and user.role != role:
        return None, api_error("Forbidden", 403)
    return user, None


@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    user = User.query.filter_by(username=(data.get("username") or "").strip()).first()
    if not user or not user.check_password(data.get("password") or ""):
        return api_error("Invalid username or password", 401)
    session.clear()
    session["user_id"] = user.id
    return jsonify(api_user(user))


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
def api_me():
    user, error = require_api_role()
    if error:
        return error
    return jsonify(api_user(user))


@app.get("/api/student/courses")
def api_student_courses():
    user, error = require_api_role("student")
    if error:
        return error
    courses = Course.query.join(Enrollment).filter(
        Enrollment.student_id == user.id
    ).order_by(Course.name).all()
    return jsonify([api_course(course) for course in courses])


@app.get("/api/courses")
def api_courses():
    user, error = require_api_role()
    if error:
        return error
    courses = Course.query.order_by(Course.name).all()
    student_id = user.id if user.role == "student" else None
    return jsonify([api_course(course, student_id) for course in courses])


@app.post("/api/student/courses/<int:course_id>")
def api_enroll(course_id: int):
    user, error = require_api_role("student")
    if error:
        return error
    ok, message = enroll_student(user.id, course_id)
    if not ok:
        status = 404 if message == "Course not found." else 409
        return api_error(message, status)
    return jsonify(api_course(db.session.get(Course, course_id), user.id))


@app.delete("/api/student/courses/<int:course_id>")
def api_drop(course_id: int):
    user, error = require_api_role("student")
    if error:
        return error
    enrollment = Enrollment.query.filter_by(
        student_id=user.id,
        course_id=course_id,
    ).first()
    if enrollment is None:
        return api_error("You are not enrolled in that course", 404)
    db.session.delete(enrollment)
    db.session.commit()
    return jsonify(api_course(db.session.get(Course, course_id), user.id))


@app.get("/api/teacher/courses")
def api_teacher_courses():
    user, error = require_api_role("teacher")
    if error:
        return error
    courses = Course.query.filter_by(teacher_id=user.id).order_by(Course.name).all()
    return jsonify([api_course(course) for course in courses])


@app.get("/api/teacher/courses/<int:course_id>")
def api_teacher_roster(course_id: int):
    user, error = require_api_role("teacher")
    if error:
        return error
    course = Course.query.filter_by(id=course_id, teacher_id=user.id).first()
    if course is None:
        return api_error("Course not found", 404)
    enrollments = Enrollment.query.filter_by(course_id=course.id).join(User).order_by(
        User.display_name
    ).all()
    students = [
        {"student_id": enrollment.student_id,
         "name": enrollment.student.display_name,
         "grade": enrollment.grade}
        for enrollment in enrollments
    ]
    return jsonify(course=api_course(course), students=students)


@app.put("/api/teacher/courses/<int:course_id>/students/<int:student_id>")
def api_set_grade(course_id: int, student_id: int):
    user, error = require_api_role("teacher")
    if error:
        return error
    course = Course.query.filter_by(id=course_id, teacher_id=user.id).first()
    if course is None:
        return api_error("Course not found", 404)
    data = request.get_json(silent=True) or {}
    grade = data.get("grade")
    if grade is not None:
        try:
            grade = float(grade)
        except (TypeError, ValueError):
            return api_error("Grade must be a number from 0 to 100", 400)
        if not 0 <= grade <= 100:
            return api_error("Grade must be a number from 0 to 100", 400)
    enrollment = Enrollment.query.filter_by(
        student_id=student_id,
        course_id=course.id,
    ).first()
    if enrollment is None:
        return api_error("Student is not enrolled in this course", 404)
    enrollment.grade = grade
    db.session.commit()
    return jsonify(student_id=student_id, course_id=course.id, grade=grade)


class SecureAdminIndexView(AdminIndexView):
    @expose("/")
    def index(self):
        user = current_user()
        if not user or user.role != "admin":
            return redirect("/")
        return super().index()


class SecureModelView(ModelView):
    def is_accessible(self):
        user = current_user()
        return bool(user and user.role == "admin")

    def inaccessible_callback(self, name, **kwargs):
        return redirect("/")


admin = Admin(app, name="ACME University Admin", index_view=SecureAdminIndexView(), url="/admin")
admin.add_view(SecureModelView(User, db.session))
admin.add_view(SecureModelView(Course, db.session))
admin.add_view(SecureModelView(Enrollment, db.session))
admin.add_link(MenuLink(name="Sign out", url="/admin/logout"))


@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    init_db()
    app.run()
