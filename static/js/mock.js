const MockServer = (() => {
  const STORAGE_KEY = "lab8-mock-db-v2";
  const SESSION_KEY = "lab8-mock-user";

  function seed() {
    const users = [
      { id: 1, username: "admin", role: "admin", display_name: "Admin" },
      { id: 2, username: "rjenkins", role: "teacher", display_name: "Ralph Jenkins" },
      { id: 3, username: "swalker", role: "teacher", display_name: "Susan Walker" },
      { id: 4, username: "ahepworth", role: "teacher", display_name: "Ammon Hepworth" },
      { id: 5, username: "schandrasekhar", role: "teacher", display_name: "Santosh Chandrasekhar" },
      { id: 10, username: "jsantos", role: "student", display_name: "Jose Santos" },
      { id: 11, username: "bbrown", role: "student", display_name: "Betty Brown" },
      { id: 12, username: "jstuart", role: "student", display_name: "John Stuart" },
      { id: 13, username: "lcheng", role: "student", display_name: "Li Cheng" },
      { id: 14, username: "nlittle", role: "student", display_name: "Nancy Little" },
      { id: 15, username: "mnorris", role: "student", display_name: "Mindy Norris" },
      { id: 16, username: "aranganath", role: "student", display_name: "Aditya Ranganath" },
      { id: 17, username: "ychen", role: "student", display_name: "Yi Wen Chen" },
      { id: 18, username: "nforce", role: "student", display_name: "Nicholas Force" },
    ];
    const courses = [
      { id: 1, name: "Math 101", teacher_id: 2, time: "MWF 10:00-10:50 AM", capacity: 8 },
      { id: 2, name: "Physics 121", teacher_id: 3, time: "TR 11:00-11:50 AM", capacity: 10 },
      { id: 3, name: "CS 106", teacher_id: 4, time: "MWF 2:00-2:50 PM", capacity: 10 },
      { id: 4, name: "CS 162", teacher_id: 4, time: "TR 3:00-3:50 PM", capacity: 4 },
      { id: 5, name: "CSE 120", teacher_id: 5, time: "W 4:30-7:20 PM", capacity: 120 },
    ];
    const enrollments = [
      // Math 101
      [10, 1, 92], [11, 1, 65], [12, 1, 86], [13, 1, 77],
      // Physics 121
      [14, 2, 53], [13, 2, 85], [15, 2, 94], [12, 2, 91], [11, 2, 88],
      // CS 106
      [16, 3, 93], [17, 3, 85], [14, 3, 57], [15, 3, 68],
      // CS 162
      [16, 4, 99], [14, 4, 87], [17, 4, 92], [12, 4, 67],
      // CSE 120 
      [18, 5, null],
    ].map(([student_id, course_id, grade]) => ({ student_id, course_id, grade }));
    return { users, courses, enrollments };
  }

  let db;

  try {
    db = JSON.parse(sessionStorage.getItem(STORAGE_KEY)) || seed();
  } catch (_) {
    db = seed();
  }

  const save = () => sessionStorage.setItem(STORAGE_KEY, JSON.stringify(db));

  const fail = (status, message) => {
    throw new ApiError(status, message);
  };

  const currentUser = () => {
    const id = Number(sessionStorage.getItem(SESSION_KEY));
    return db.users.find((u) => u.id === id) || null;
  };

  const requireRole = (role) => {
    const u = currentUser();
    if (!u) fail(401, "Not logged in");
    if (u.role !== role) fail(403, "Forbidden");
    return u;
  };

  const publicUser = (u) => ({
    id: u.id, username: u.username, role: u.role, display_name: u.display_name,
  });

  const courseView = (c, studentId) => ({
    id: c.id,
    name: c.name,
    teacher: db.users.find((u) => u.id === c.teacher_id).display_name,
    time: c.time,
    enrolled: db.enrollments.filter((e) => e.course_id === c.id).length,
    capacity: c.capacity,
    ...(studentId !== undefined && {
      is_enrolled: db.enrollments.some((e) => e.course_id === c.id && e.student_id === studentId),
    }),
  });

  // Each route: [method, regex, handler(match, body)]
  const routes = [
    ["POST", /^\/api\/login$/, (_, body) => {
      const u = db.users.find((x) => x.username === (body?.username || "").trim());
      if (!u || body.password !== "password123") fail(401, "Invalid username or password");
      sessionStorage.setItem(SESSION_KEY, u.id);
      return publicUser(u);
    }],

    ["POST", /^\/api\/logout$/, () => {
      sessionStorage.removeItem(SESSION_KEY);
      return { ok: true };
    }],

    ["GET", /^\/api\/me$/, () => {
      const u = currentUser();
      if (!u) fail(401, "Not logged in");
      return publicUser(u);
    }],


    // ----- Student -----
    ["GET", /^\/api\/student\/courses$/, () => {
      const u = requireRole("student");
      const ids = db.enrollments.filter((e) => e.student_id === u.id).map((e) => e.course_id);
      return db.courses.filter((c) => ids.includes(c.id)).map((c) => courseView(c));
    }],

    ["GET", /^\/api\/courses$/, () => {
      const u = currentUser();
      if (!u) fail(401, "Not logged in");
      return db.courses.map((c) => courseView(c, u.role === "student" ? u.id : undefined));
    }],

    ["POST", /^\/api\/student\/courses\/(\d+)$/, (m) => {
      const u = requireRole("student");
      const c = db.courses.find((x) => x.id === Number(m[1]));
      if (!c) fail(404, "Course not found");
      const taken = db.enrollments.filter((e) => e.course_id === c.id);
      if (taken.some((e) => e.student_id === u.id)) fail(409, `You are already enrolled in ${c.name}`);
      if (taken.length >= c.capacity) fail(409, `${c.name} is full`);
      db.enrollments.push({ student_id: u.id, course_id: c.id, grade: null });
      save();
      return courseView(c, u.id);
    }],

    ["DELETE", /^\/api\/student\/courses\/(\d+)$/, (m) => {
      const u = requireRole("student");
      const cid = Number(m[1]);
      const idx = db.enrollments.findIndex((e) => e.course_id === cid && e.student_id === u.id);
      if (idx === -1) fail(404, "You are not enrolled in that course");
      db.enrollments.splice(idx, 1);
      save();
      return courseView(db.courses.find((c) => c.id === cid), u.id);
    }],


    // ----- Teacher -----
    ["GET", /^\/api\/teacher\/courses$/, () => {
      const u = requireRole("teacher");
      return db.courses.filter((c) => c.teacher_id === u.id).map((c) => courseView(c));
    }],

    ["GET", /^\/api\/teacher\/courses\/(\d+)$/, (m) => {
      const u = requireRole("teacher");
      const c = db.courses.find((x) => x.id === Number(m[1]));

      if (!c || c.teacher_id !== u.id) fail(404, "Course not found");
      const students = db.enrollments
        .filter((e) => e.course_id === c.id)
        .map((e) => ({
          student_id: e.student_id,
          name: db.users.find((x) => x.id === e.student_id).display_name,
          grade: e.grade,
        }));
      return { course: courseView(c), students };
    }],

    ["PUT", /^\/api\/teacher\/courses\/(\d+)\/students\/(\d+)$/, (m, body) => {
      const u = requireRole("teacher");
      const c = db.courses.find((x) => x.id === Number(m[1]));

      if (!c || c.teacher_id !== u.id) fail(404, "Course not found");
      const e = db.enrollments.find((x) => x.course_id === c.id && x.student_id === Number(m[2]));

      if (!e) fail(404, "Student is not enrolled in this course");
      const g = body?.grade;

      if (g !== null && (typeof g !== "number" || !Number.isFinite(g) || g < 0 || g > 100)) {
        fail(400, "Grade must be a number from 0 to 100");
      }
      
      e.grade = g;
      save();
      return { student_id: e.student_id, course_id: c.id, grade: e.grade };
    }],
  ];

  async function handle(method, path, body) {
    await new Promise((r) => setTimeout(r, 120)); // simulate network delay
    for (const [m, re, fn] of routes) {
      const match = path.match(re);
      if (m === method && match) return structuredClone(fn(match, body));
    }
    fail(404, `No mock route for ${method} ${path}`);
  }

  return { handle };
})();
