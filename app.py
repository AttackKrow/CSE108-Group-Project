from typing import Optional

from functools import wraps
import os
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin, AdminIndexView, expose
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

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///enrollment.db"

db = SQLAlchemy(app)


def current_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


def login_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                return redirect(url_for("login", next=request.path))
            if roles and user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


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


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


@app.route("/")
def index():
    if current_user():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session.clear()
            session["user_id"] = user.id
            destination = request.args.get("next")
            if destination and destination.startswith("/") and not destination.startswith("//"):
                return redirect(destination)
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required("student", "teacher", "admin")
def dashboard():
    user = current_user()
    if user.role == "teacher":
        courses = Course.query.filter_by(teacher_id=user.id).order_by(Course.name).all()
        return render_template("teacher.html", courses=courses)
    if user.role == "admin":
        return redirect(url_for("admin.index"))
    enrolled_ids = db.session.query(Enrollment.course_id).filter_by(student_id=user.id)
    enrolled = Course.query.filter(Course.id.in_(enrolled_ids)).order_by(Course.name).all()
    available = Course.query.order_by(Course.name).all()
    return render_template("student.html", enrolled=enrolled, courses=available)


@app.post("/courses/<int:course_id>/enroll")
@login_required("student")
def enroll(course_id):
    ok, message = enroll_student(current_user().id, course_id)
    flash(message, "success" if ok else "error")
    return redirect(url_for("dashboard"))


@app.post("/courses/<int:course_id>/drop")
@login_required("student")
def drop_course(course_id):
    enrollment = Enrollment.query.filter_by(student_id=current_user().id, course_id=course_id).first()
    if enrollment:
        db.session.delete(enrollment)
        db.session.commit()
        flash("Course dropped.", "success")
    else:
        flash("You are not enrolled in that course.", "error")
    return redirect(url_for("dashboard"))


@app.route("/courses/<int:course_id>", methods=["GET", "POST"])
@login_required("teacher")
def course_roster(course_id):
    course = Course.query.filter_by(id=course_id, teacher_id=current_user().id).first_or_404()
    if request.method == "POST":
        try:
            grade = float(request.form["grade"])
            if not 0 <= grade <= 100:
                raise ValueError
            ok, message = update_grade(int(request.form["student_id"]), course.id, grade)
            flash(message, "success" if ok else "error")
        except (KeyError, ValueError):
            flash("Enter a grade from 0 to 100.", "error")
        return redirect(url_for("course_roster", course_id=course.id))
    enrollments = Enrollment.query.filter_by(course_id=course.id).join(User).order_by(User.display_name).all()
    return render_template("roster.html", course=course, enrollments=enrollments)


class SecureAdminIndexView(AdminIndexView):
    @expose("/")
    def index(self):
        user = current_user()
        if not user or user.role != "admin":
            return redirect(url_for("login"))
        return super().index()


class SecureModelView(ModelView):
    def is_accessible(self):
        user = current_user()
        return bool(user and user.role == "admin")

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("login"))


admin = Admin(app, name="ACME University Admin", index_view=SecureAdminIndexView(), url="/admin")
admin.add_view(SecureModelView(User, db.session))
admin.add_view(SecureModelView(Course, db.session))
admin.add_view(SecureModelView(Enrollment, db.session))


if __name__ == "__main__":
    init_db()
    app.run()
