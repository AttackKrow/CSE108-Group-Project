const appEl = document.getElementById("app");
const topbarEl = document.getElementById("topbar");
const welcomeEl = document.getElementById("welcome");
const toastEl = document.getElementById("toast");

let currentUser = null;

// ---------- Helpers ----------

// Escape text before putting it into innerHTML (prevents broken HTML / XSS).
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}

let toastTimer;
function toast(message, isError = false) {
  toastEl.textContent = message;
  toastEl.classList.toggle("error", isError);
  toastEl.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.add("hidden"), 3000);
}

function go(hash) {
  if (location.hash === hash) router();
  else location.hash = hash;
}

function homeFor(user) {
  return user.role === "teacher" ? "#/teacher" : "#/student";
}

function welcomeText(user) {
  const parts = user.display_name.trim().split(/\s+/);
  if (user.role === "teacher") return `Welcome Prof. ${parts[parts.length - 1]}!`;
  return `Welcome ${parts[0]}!`;
}

function showLoading() {
  appEl.innerHTML = `<div class="card empty">Loading…</div>`;
}

// When the session has expired, any request returns 401: send the user back to login.
function handleError(err) {
  if (err.status === 401) {
    currentUser = null;
    go("#/login");
    return;
  }
  toast(err.message, true);
}

function courseTable(courses, { actions, clickable = false, emptyText }) {
  if (courses.length === 0) {
    return `<div class="empty">${esc(emptyText)}</div>`;
  }

  const rows = courses.map((c) => {
    const isFull = c.enrolled >= c.capacity;
    return `
      <tr ${clickable ? `class="clickable" data-course-id="${c.id}"` : ""}>
        <td>${esc(c.name)}</td>
        <td>${esc(c.teacher)}</td>
        <td>${esc(c.time)}</td>
        <td class="${isFull ? "full" : ""}">${c.enrolled}/${c.capacity}</td>
        ${actions ? `<td>${actions(c, isFull)}</td>` : ""}
      </tr>`;
  }).join("");

  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Course Name</th><th>Teacher</th><th>Time</th><th>Students Enrolled</th>
            ${actions ? "<th></th>" : ""}
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

// ---------- Views ----------

function renderLogin() {
  topbarEl.classList.add("hidden");
  appEl.innerHTML = `
    <form id="login-form" class="card login-card" novalidate>
      <h1>UC Merced</h1>
      <div class="form-row">
        <label for="username">Username</label>
        <input id="username" name="username" autocomplete="username" required>
      </div>
      <div class="form-row">
        <label for="password">Password</label>
        <input id="password" name="password" type="password" autocomplete="current-password" required>
      </div>
      <p id="login-error" class="form-error"></p>
      <button class="btn btn-block" type="submit">Sign in</button>
      ${USE_MOCK ? `<p class="hint">Mock mode: try <b>mnorris</b> or <b>ahepworth</b> with password <b>password123</b></p>` : ""}
    </form>`;

  const form = document.getElementById("login-form");
  const errorEl = document.getElementById("login-error");
  form.username.focus();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = form.username.value.trim();
    const password = form.password.value;

    if (!username || !password) {
      errorEl.textContent = "Please enter your username and password.";
      return;
    }

    const btn = form.querySelector("button");
    btn.disabled = true;
    errorEl.textContent = "";

    try {
      currentUser = await api.login(username, password);
      if (currentUser.role === "admin") {
        // Admins use the Flask-Admin page served by the backend.
        if (USE_MOCK) {
          errorEl.textContent = "Admin uses Flask-Admin at /admin (not available in mock mode).";
          await api.logout();
          currentUser = null;
          return;
        }
        window.location.href = "/admin";
        return;
      }
      go(homeFor(currentUser));
    } catch (err) {
      errorEl.textContent = err.status === 401 ? "Invalid username or password." : err.message;
    } finally {
      btn.disabled = false;
    }
  });
}

function showTopbar() {
  welcomeEl.textContent = welcomeText(currentUser);
  topbarEl.classList.remove("hidden");
}

async function renderStudent(tab) {
  showTopbar();
  const isMine = tab === "mine";
  appEl.innerHTML = `
    <div class="tabs">
      <button class="tab ${isMine ? "active" : ""}" data-href="#/student">Your Courses</button>
      <button class="tab ${!isMine ? "active" : ""}" data-href="#/student/add">Add Courses</button>
    </div>
    <div class="card" id="student-panel"><div class="empty">Loading…</div></div>`;

  const panel = document.getElementById("student-panel");
  try {
    if (isMine) {
      const courses = await api.myCourses();
      panel.innerHTML = courseTable(courses, {
        emptyText: "You are not enrolled in any courses yet. Use “Add Courses” to sign up.",
        actions: (c) =>
          `<button class="btn btn-danger btn-small" data-drop="${c.id}" data-name="${esc(c.name)}">Drop</button>`,
      });
    } else {
      const courses = await api.allCourses();
      panel.innerHTML = courseTable(courses, {
        emptyText: "No courses are offered right now.",
        actions: (c, isFull) => {
          if (c.is_enrolled) return `<span class="badge">Enrolled</span>`;
          if (isFull) return `<button class="btn btn-small" disabled>Full</button>`;
          return `<button class="btn btn-small" data-enroll="${c.id}">Add</button>`;
        },
      });
    }
  } catch (err) {
    handleError(err);
  }
}

async function renderTeacherCourses() {
  showTopbar();
  showLoading();
  try {
    const courses = await api.teachingCourses();
    appEl.innerHTML = `
      <div class="card">
        <h2>Your Courses</h2>
        <p class="subtitle">Click a course to see its students and grades.</p>
        ${courseTable(courses, { clickable: true, emptyText: "You are not teaching any courses." })}
      </div>`;
  } catch (err) {
    handleError(err);
  }
}

async function renderRoster(courseId) {
  showTopbar();
  showLoading();
  try {
    const { course, students } = await api.roster(courseId);
    const rows = students.map((s) => `
      <tr>
        <td>${esc(s.name)}</td>
        <td>
          <form class="grade-cell" data-student-id="${s.student_id}" data-name="${esc(s.name)}">
            <input class="grade-input" type="number" min="0" max="100" step="any"
                   value="${s.grade ?? ""}" aria-label="Grade for ${esc(s.name)}">
            <button class="btn btn-small" type="submit">Save</button>
          </form>
        </td>
      </tr>`).join("");

    appEl.innerHTML = `
      <a href="#/teacher" class="back">← Back to your courses</a>
      <div class="card" data-course-id="${course.id}">
        <h2>${esc(course.name)}</h2>
        <p class="subtitle">${esc(course.time)} · ${course.enrolled}/${course.capacity} students</p>
        ${students.length === 0
          ? `<div class="empty">No students are enrolled in this course.</div>`
          : `<div class="table-wrap"><table>
               <thead><tr><th>Student Name</th><th>Grade</th></tr></thead>
               <tbody>${rows}</tbody>
             </table></div>`}
      </div>`;
  } catch (err) {
    if (err.status === 404 || err.status === 403) {
      toast(err.message, true);
      go("#/teacher");
    } else {
      handleError(err);
    }
  }
}

// ---------- Event handling (event delegation on #app) ----------

appEl.addEventListener("click", async (e) => {
  const tabBtn = e.target.closest("[data-href]");
  if (tabBtn) {
    go(tabBtn.dataset.href);
    return;
  }

  const enrollBtn = e.target.closest("[data-enroll]");
  if (enrollBtn) {
    enrollBtn.disabled = true;
    try {
      const course = await api.enroll(enrollBtn.dataset.enroll);
      toast(`Enrolled in ${course.name}`);
    } catch (err) {
      handleError(err);
    }
    renderStudent("add"); // refresh counts either way (someone may have taken the last seat)
    return;
  }

  const dropBtn = e.target.closest("[data-drop]");
  if (dropBtn) {
    if (!confirm(`Drop ${dropBtn.dataset.name}?`)) return;
    dropBtn.disabled = true;
    try {
      const course = await api.drop(dropBtn.dataset.drop);
      toast(`Dropped ${course.name}`);
    } catch (err) {
      handleError(err);
    }
    renderStudent("mine");
    return;
  }

  const row = e.target.closest("tr.clickable[data-course-id]");
  if (row) {
    go(`#/teacher/course/${row.dataset.courseId}`);
  }
});

appEl.addEventListener("submit", async (e) => {
  const form = e.target.closest("form.grade-cell");
  if (!form) return;
  e.preventDefault();

  const input = form.querySelector("input");
  const raw = input.value.trim();
  const grade = raw === "" ? null : Number(raw);
  if (grade !== null && (!Number.isFinite(grade) || grade < 0 || grade > 100)) {
    toast("Grade must be a number from 0 to 100", true);
    input.focus();
    return;
  }

  const courseId = form.closest("[data-course-id]").dataset.courseId;
  const btn = form.querySelector("button");
  btn.disabled = true;

  try {
    const saved = await api.setGrade(courseId, form.dataset.studentId, grade);
    input.value = saved.grade ?? "";
    toast(`Saved grade for ${form.dataset.name}`);
  } catch (err) {
    handleError(err);
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  try {
    await api.logout();
  } catch (_) {
    /* log out locally even if the request fails */
  }
  currentUser = null;
  go("#/login");
});

// ---------- Router ----------

async function router() {
  const hash = location.hash || "#/login";

  // On first load (or after a reload), ask the server who is logged in.
  if (!currentUser && hash !== "#/login") {
    try {
      currentUser = await api.me();
    } catch (_) {
      go("#/login");
      return;
    }
  }

  // Admins don't use these pages; they belong on Flask-Admin.
  if (currentUser && currentUser.role === "admin") {
    if (!USE_MOCK) {
      window.location.href = "/admin";
      return;
    }
    await api.logout();
    currentUser = null;
    if (hash !== "#/login") return go("#/login");
  }

  if (hash === "#/login") {
    if (currentUser) return go(homeFor(currentUser));
    return renderLogin();
  }

  // Send users to their own area if they type another role's URL.
  if (hash.startsWith("#/student") && currentUser.role !== "student") return go(homeFor(currentUser));
  if (hash.startsWith("#/teacher") && currentUser.role !== "teacher") return go(homeFor(currentUser));

  if (hash === "#/student") return renderStudent("mine");
  if (hash === "#/student/add") return renderStudent("add");
  if (hash === "#/teacher") return renderTeacherCourses();

  const m = hash.match(/^#\/teacher\/course\/(\d+)$/);
  if (m) return renderRoster(m[1]);

  go(homeFor(currentUser)); // unknown route
}

window.addEventListener("hashchange", router);

if (USE_MOCK) {
  document.body.insertAdjacentHTML(
    "afterbegin",
    `<div class="mock-banner">Mock mode — using built-in sample data, not the Flask server</div>`
  );
}

router();
