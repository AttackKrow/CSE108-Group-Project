from typing import Optional

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
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

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///enrollment.db"

db = SQLAlchemy(app)


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


if __name__ == "__main__":
    init_db()
