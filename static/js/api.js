const USE_MOCK =
  new URLSearchParams(location.search).has("mock") || location.protocol === "file:";

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function request(method, path, body) {
  if (USE_MOCK) {
    return MockServer.handle(method, path, body);
  }

  const options = {
    method,
    credentials: "same-origin", // send the Flask session cookie
    headers: {},
  };

  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  const res = await fetch(path, options);

  let data = null;
  
  try {
    data = await res.json();
  } catch (_) {
    /* empty or non-JSON body */
  }

  if (!res.ok) {
    throw new ApiError(res.status, (data && data.error) || `Request failed (${res.status})`);
  }
  return data;
}

const api = {
  // ----- Auth -----
  login: (username, password) => request("POST", "/api/login", { username, password }),
  logout: () => request("POST", "/api/logout"),
  me: () => request("GET", "/api/me"),

  // ----- Student -----
  myCourses: () => request("GET", "/api/student/courses"),
  allCourses: () => request("GET", "/api/courses"),
  enroll: (courseId) => request("POST", `/api/student/courses/${courseId}`),
  drop: (courseId) => request("DELETE", `/api/student/courses/${courseId}`),

  // ----- Teacher -----
  teachingCourses: () => request("GET", "/api/teacher/courses"),
  roster: (courseId) => request("GET", `/api/teacher/courses/${courseId}`),
  setGrade: (courseId, studentId, grade) =>
    request("PUT", `/api/teacher/courses/${courseId}/students/${studentId}`, { grade }),
};
