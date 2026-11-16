import csv
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import Course, Enrollment, User, app, db

DEFAULT_PASSWORD = "password123"
_LOCAL_SEED_CSV_PATH = Path(__file__).with_name("seed_data.csv")
DEFAULT_SEED_CSV_PATH = (
    _LOCAL_SEED_CSV_PATH
    if _LOCAL_SEED_CSV_PATH.exists()
    else PROJECT_ROOT / "seed_data.csv"
)


def make_username(display_name: str) -> str:
    """Build a deterministic lowercase username (first initial + last name)."""
    parts = display_name.strip().split()
    if not parts:
        raise ValueError("Display name cannot be empty.")
    if len(parts) == 1:
        return parts[0].lower()
    return f"{parts[0][0].lower()}{parts[-1].lower()}"


def _get_or_create_user(
    username: str,
    role: str,
    display_name: str,
    password: str = DEFAULT_PASSWORD,
) -> User:
    """Return an existing user by username or stage a new one with a hashed password."""
    user = User.query.filter_by(username=username).first()
    if user is None:
        user = User(username=username, role=role, display_name=display_name.strip())
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
    return user


def _get_or_create_course(
    name: str,
    teacher_id: int,
    time: str,
    capacity: int,
) -> Course:
    """Return an existing course by name or stage a new course offering."""
    course = Course.query.filter_by(name=name).first()
    if course is None:
        course = Course(
            name=name,
            teacher_id=teacher_id,
            time=time,
            capacity=capacity,
        )
        db.session.add(course)
        db.session.flush()
    return course


def _read_seed_rows(csv_path: Optional[Path | str] = None) -> list[dict[str, str]]:
    """Load CSV seed rows from seed_data.csv or the specified path."""
    target_path = Path(csv_path) if csv_path is not None else DEFAULT_SEED_CSV_PATH
    with target_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def seed_db(csv_path: Optional[Path | str] = None, reset: bool = False) -> None:
    """Populate users, courses, and enrollments from the workbook CSV."""
    with app.app_context():
        if reset:
            db.drop_all()
        db.create_all()

        _get_or_create_user("admin", "admin", "Admin")

        current_class = ""
        current_teacher = ""
        current_time = ""
        current_capacity = ""

        for raw_row in _read_seed_rows(csv_path):
            row = {k: (v or "").strip() for k, v in raw_row.items() if k is not None}
            if not any(row.values()):
                continue

            if row.get("Class Name"):
                current_class = row["Class Name"]
            if row.get("Teacher Name"):
                current_teacher = row["Teacher Name"]
            if row.get("Time"):
                current_time = row["Time"]
            if row.get("Capacity"):
                current_capacity = row["Capacity"]

            if not (current_class and current_teacher and current_time and current_capacity):
                raise ValueError(f"Incomplete course metadata before row: {row}")

            teacher = _get_or_create_user(
                make_username(current_teacher),
                "teacher",
                current_teacher,
            )
            course = _get_or_create_course(
                current_class,
                teacher.id,
                current_time,
                int(current_capacity),
            )

            student_name = row.get("Student Names", "")
            if not student_name:
                continue

            student = _get_or_create_user(
                make_username(student_name),
                "student",
                student_name,
            )
            grade_str = row.get("Grades", "")
            grade = float(grade_str) if grade_str else None

            enrollment = Enrollment.query.filter_by(
                student_id=student.id,
                course_id=course.id,
            ).first()
            if enrollment is None:
                db.session.add(
                    Enrollment(
                        student_id=student.id,
                        course_id=course.id,
                        grade=grade,
                    )
                )
            else:
                enrollment.grade = grade

        db.session.commit()


if __name__ == "__main__":
    seed_db(reset=True)
