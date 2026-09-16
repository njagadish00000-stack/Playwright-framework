"""Bundled demo application: REST API + web UI used by the example tests.

The demo app exists so the framework is **runnable anywhere, including fully
offline environments**: API tests exercise a real HTTP API and UI tests drive
real pages in a real browser. Point ``BASE_URL`` / ``API_BASE_URL`` at your own
system under test to run the same suite against a real product.

Run standalone:
    python -m server.demo_app [--host 127.0.0.1] [--port 8765]

The pytest session fixture (``demo_app`` in conftest.py) starts this app
automatically in a background thread when the configured URLs point at
localhost, so example tests "just work".
"""

from __future__ import annotations

import contextlib
import functools
import io
import threading
import time
from typing import Any

from flask import Flask, Response, jsonify, request

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo123"
DEMO_TOKEN = "demo-token-12345"

_SEED_USERS = [
    {"id": i, "name": name, "username": uname, "email": f"{uname}@example.com",
     "role": "admin" if i == 1 else "user"}
    for i, (name, uname) in enumerate(
        [
            ("Alice Anderson", "alice"), ("Bob Brown", "bob"),
            ("Carol Clark", "carol"), ("Dave Davis", "dave"),
            ("Erin Evans", "erin"), ("Frank Foster", "frank"),
            ("Grace Green", "grace"), ("Hank Hill", "hank"),
            ("Ivy Irving", "ivy"), ("Jack Jones", "jack"),
        ],
        start=1,
    )
]

_SEED_POSTS = [
    {"id": i, "userId": ((i - 1) % 10) + 1, "title": f"Demo post {i}",
     "body": f"This is the body of demo post {i}."}
    for i in range(1, 11)
]


class DemoStore:
    """Thread-safe in-memory data store."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.users: dict[int, dict] = {u["id"]: dict(u) for u in _SEED_USERS}
            self.posts: dict[int, dict] = {p["id"]: dict(p) for p in _SEED_POSTS}
            self.next_user_id = max(self.users) + 1
            self.next_post_id = max(self.posts) + 1


store = DemoStore()


def create_app() -> Flask:
    app = Flask("demo_app")

    # ------------------------------------------------------------------ helpers
    def bearer_required(view):
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if auth != f"Bearer {DEMO_TOKEN}":
                return jsonify({"error": "missing or invalid bearer token"}), 401
            return view(*args, **kwargs)

        return wrapper

    # ------------------------------------------------------------------ health
    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "app": "demo-app", "time": time.time()})

    @app.post("/api/_reset")
    def reset_data():
        """Test-only endpoint: restore seeded users/posts."""
        store.reset()
        return jsonify({"status": "reset"})

    # ------------------------------------------------------------------ auth
    @app.post("/api/login")
    def login():
        payload = request.get_json(silent=True) or {}
        if payload.get("username") == DEMO_USERNAME and payload.get("password") == DEMO_PASSWORD:
            return jsonify({"token": DEMO_TOKEN, "username": DEMO_USERNAME})
        return jsonify({"error": "invalid credentials"}), 401

    @app.get("/api/profile")
    @bearer_required
    def profile():
        return jsonify({"username": DEMO_USERNAME, "role": "admin"})

    @app.get("/api/basic-auth")
    def basic_auth():
        auth = request.authorization
        if auth and auth.username == DEMO_USERNAME and auth.password == DEMO_PASSWORD:
            return jsonify({"authenticated": True, "user": auth.username})
        return Response(
            jsonify({"error": "basic auth required"}).get_data(),
            status=401, mimetype="application/json",
            headers={"WWW-Authenticate": 'Basic realm="demo"'},
        )

    @app.get("/api/echo-headers")
    def echo_headers():
        return jsonify({k: v for k, v in request.headers.items()})

    @app.post("/api/echo")
    def echo():
        return jsonify({
            "json": request.get_json(silent=True),
            "form": request.form.to_dict(),
            "args": request.args.to_dict(),
            "headers": {k: v for k, v in request.headers.items()
                        if k.lower() in {"x-custom-header", "content-type"}},
        })

    @app.post("/api/upload")
    def upload():
        if "file" not in request.files:
            return jsonify({"error": "no file part named 'file'"}), 400
        uploaded = request.files["file"]
        content = uploaded.read()
        return jsonify({
            "filename": uploaded.filename,
            "size": len(content),
            "content_type": uploaded.content_type,
        }), 201

    @app.get("/api/delay/<int:seconds>")
    def delay(seconds: int):
        time.sleep(min(seconds, 5))
        return jsonify({"slept": seconds})

    # ------------------------------------------------------------------ users
    @app.get("/api/users")
    def list_users():
        with store._lock:
            users = list(store.users.values())
        role = request.args.get("role")
        if role:
            users = [u for u in users if u.get("role") == role]
        limit = request.args.get("_limit")
        if limit:
            try:
                users = users[: int(limit)]
            except ValueError:
                return jsonify({"error": "_limit must be an integer"}), 400
        return jsonify(users)

    @app.post("/api/users")
    def create_user():
        payload = request.get_json(silent=True) or {}
        missing = [f for f in ("name", "username", "email") if not payload.get(f)]
        if missing:
            return jsonify({"error": f"missing fields: {', '.join(missing)}"}), 400
        with store._lock:
            if any(u["username"] == payload["username"] for u in store.users.values()):
                return jsonify({"error": "username already exists"}), 409
            user = {
                "id": store.next_user_id,
                "name": payload["name"],
                "username": payload["username"],
                "email": payload["email"],
                "role": payload.get("role", "user"),
            }
            store.users[user["id"]] = user
            store.next_user_id += 1
        return jsonify(user), 201

    @app.get("/api/users/<int:user_id>")
    def get_user(user_id: int):
        with store._lock:
            user = store.users.get(user_id)
        if not user:
            return jsonify({"error": "user not found"}), 404
        return jsonify(user)

    @app.put("/api/users/<int:user_id>")
    def put_user(user_id: int):
        payload = request.get_json(silent=True) or {}
        with store._lock:
            if user_id not in store.users:
                return jsonify({"error": "user not found"}), 404
            missing = [f for f in ("name", "username", "email") if not payload.get(f)]
            if missing:
                return jsonify({"error": f"missing fields: {', '.join(missing)}"}), 400
            user = {"id": user_id, "name": payload["name"],
                    "username": payload["username"], "email": payload["email"],
                    "role": payload.get("role", "user")}
            store.users[user_id] = user
        return jsonify(user)

    @app.patch("/api/users/<int:user_id>")
    def patch_user(user_id: int):
        payload = request.get_json(silent=True) or {}
        with store._lock:
            if user_id not in store.users:
                return jsonify({"error": "user not found"}), 404
            user = store.users[user_id]
            for key in ("name", "username", "email", "role"):
                if key in payload:
                    user[key] = payload[key]
        return jsonify(user)

    @app.delete("/api/users/<int:user_id>")
    def delete_user(user_id: int):
        with store._lock:
            if user_id not in store.users:
                return jsonify({"error": "user not found"}), 404
            del store.users[user_id]
        return "", 204

    # ------------------------------------------------------------------ posts
    @app.get("/api/posts")
    def list_posts():
        with store._lock:
            posts = list(store.posts.values())
        user_id = request.args.get("userId")
        if user_id:
            posts = [p for p in posts if str(p.get("userId")) == user_id]
        return jsonify(posts)

    @app.post("/api/posts")
    def create_post():
        payload = request.get_json(silent=True) or {}
        missing = [f for f in ("userId", "title", "body") if payload.get(f) is None]
        if missing:
            return jsonify({"error": f"missing fields: {', '.join(missing)}"}), 400
        with store._lock:
            post = {"id": store.next_post_id, "userId": payload["userId"],
                    "title": payload["title"], "body": payload["body"]}
            store.posts[post["id"]] = post
            store.next_post_id += 1
        return jsonify(post), 201

    @app.get("/api/posts/<int:post_id>")
    def get_post(post_id: int):
        with store._lock:
            post = store.posts.get(post_id)
        if not post:
            return jsonify({"error": "post not found"}), 404
        return jsonify(post)

    @app.put("/api/posts/<int:post_id>")
    def put_post(post_id: int):
        payload = request.get_json(silent=True) or {}
        with store._lock:
            if post_id not in store.posts:
                return jsonify({"error": "post not found"}), 404
            post = {"id": post_id, "userId": payload.get("userId", 1),
                    "title": payload.get("title", ""), "body": payload.get("body", "")}
            store.posts[post_id] = post
        return jsonify(post)

    @app.patch("/api/posts/<int:post_id>")
    def patch_post(post_id: int):
        payload = request.get_json(silent=True) or {}
        with store._lock:
            if post_id not in store.posts:
                return jsonify({"error": "post not found"}), 404
            post = store.posts[post_id]
            for key in ("userId", "title", "body"):
                if key in payload:
                    post[key] = payload[key]
        return jsonify(post)

    @app.delete("/api/posts/<int:post_id>")
    def delete_post(post_id: int):
        with store._lock:
            if post_id not in store.posts:
                return jsonify({"error": "post not found"}), 404
            del store.posts[post_id]
        return "", 204

    # ------------------------------------------------------------------ web UI
    @app.get("/")
    def home():
        return Response(HOME_HTML, mimetype="text/html")

    @app.get("/forms")
    def forms():
        return Response(FORMS_HTML, mimetype="text/html")

    @app.get("/login")
    def login_page():
        return Response(LOGIN_HTML, mimetype="text/html")

    @app.get("/users")
    def users_page():
        return Response(USERS_HTML, mimetype="text/html")

    @app.get("/download/sample.txt")
    def download_sample():
        return Response(
            "Sample download file for automation testing.\n",
            mimetype="text/plain",
            headers={"Content-Disposition": "attachment; filename=sample.txt"},
        )

    return app


# ---------------------------------------------------------------------- pages
_NAV = """
<nav data-testid="main-nav">
  <a href="/">Home</a>
  <a href="/forms">Forms</a>
  <a href="/login">Login</a>
  <a href="/users">Users</a>
</nav>
"""

_BASE_STYLE = """
<style>
  body { font-family: Arial, sans-serif; margin: 0; padding: 0 24px 60px; }
  nav { background: #1f2937; padding: 12px; margin: 0 -24px 24px; }
  nav a { color: #fff; margin-right: 16px; text-decoration: none; }
  footer { margin-top: 40px; color: #666; border-top: 1px solid #ddd; padding-top: 12px; }
  .card { border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin: 8px 0; max-width: 420px; }
  label { display: block; margin: 10px 0 4px; }
  input, select, textarea { padding: 8px; width: 320px; max-width: 100%; }
  button { padding: 10px 18px; margin-top: 12px; cursor: pointer; }
  table { border-collapse: collapse; margin-top: 12px; }
  th, td { border: 1px solid #ccc; padding: 8px 12px; }
  .error { color: #b91c1c; font-weight: bold; }
  .success { color: #15803d; font-weight: bold; }
</style>
"""

HOME_HTML = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Demo App - Home</title>{_BASE_STYLE}</head>
<body>
{_NAV}
<h1 data-testid="home-heading">Welcome to the Demo App</h1>
<div data-testid="welcome-banner">A tiny demo site for UI automation practice.</div>
<div class="card" data-testid="feature-card"><h3>Fast</h3><p>Local pages load instantly.</p></div>
<div class="card" data-testid="feature-card"><h3>Reliable</h3><p>Stable test ids on every element.</p></div>
<div class="card" data-testid="feature-card"><h3>Complete</h3><p>Forms, login and data tables.</p></div>
<p><a href="/download/sample.txt" data-testid="link-download">Download sample file</a></p>
<footer data-testid="page-footer">Demo App footer - automation friendly</footer>
</body></html>
"""

FORMS_HTML = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Demo App - Forms</title>{_BASE_STYLE}</head>
<body>
{_NAV}
<h1>Practice Form</h1>
<form id="demo-form" novalidate>
  <label for="name">Full name</label>
  <input id="name" data-testid="input-name" name="name" type="text" autocomplete="off">
  <label for="email">Email</label>
  <input id="email" data-testid="input-email" name="email" type="text" autocomplete="off">
  <label for="role">Role</label>
  <select id="role" data-testid="select-role" name="role">
    <option value="user">user</option>
    <option value="admin">admin</option>
    <option value="editor">editor</option>
  </select>
  <label for="bio">Bio</label>
  <textarea id="bio" data-testid="textarea-bio" name="bio"></textarea>
  <label><input id="newsletter" data-testid="check-newsletter" type="checkbox" checked> Subscribe to newsletter</label>
  <label for="avatar">Avatar (optional upload)</label>
  <input id="avatar" data-testid="input-avatar" type="file">
  <br><button type="submit" data-testid="btn-submit">Submit</button>
</form>
<div id="form-error" class="error" data-testid="form-error" hidden></div>
<div id="form-success" class="success" data-testid="form-success" hidden></div>
<table id="submitted" data-testid="submitted-data" hidden>
  <tr><th>Field</th><th>Value</th></tr>
  <tbody id="submitted-body"></tbody>
</table>
<script>
document.getElementById('demo-form').addEventListener('submit', function (e) {{
  e.preventDefault();
  var name = document.getElementById('name').value.trim();
  var email = document.getElementById('email').value.trim();
  var role = document.getElementById('role').value;
  var err = document.getElementById('form-error');
  var ok = document.getElementById('form-success');
  var table = document.getElementById('submitted');
  err.hidden = true; ok.hidden = true; table.hidden = true;
  if (!name) {{ err.textContent = 'Name is required.'; err.hidden = false; return; }}
  if (email.indexOf('@') === -1) {{ err.textContent = 'Enter a valid email address.'; err.hidden = false; return; }}
  ok.textContent = 'Form submitted successfully for ' + name + '.';
  ok.hidden = false;
  var body = document.getElementById('submitted-body');
  body.innerHTML = '';
  [['name', name], ['email', email], ['role', role]].forEach(function (row) {{
    var tr = document.createElement('tr');
    tr.innerHTML = '<td>' + row[0] + '</td><td>' + row[1] + '</td>';
    body.appendChild(tr);
  }});
  table.hidden = false;
}});
</script>
<footer data-testid="page-footer">Demo App footer - automation friendly</footer>
</body></html>
"""

LOGIN_HTML = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Demo App - Login</title>{_BASE_STYLE}</head>
<body>
{_NAV}
<h1>Login</h1>
<div id="login-form-wrap">
  <label for="username">Username</label>
  <input id="username" data-testid="input-username" type="text" autocomplete="off">
  <label for="password">Password</label>
  <input id="password" data-testid="input-password" type="password">
  <br><button id="login-btn" data-testid="btn-login">Log in</button>
</div>
<div id="login-error" class="error" data-testid="login-error" hidden></div>
<div id="profile" hidden>
  <h2 data-testid="profile-greeting"></h2>
  <button id="logout-btn" data-testid="btn-logout">Log out</button>
</div>
<script>
function showProfile(username) {{
  document.getElementById('login-form-wrap').hidden = true;
  document.getElementById('login-error').hidden = true;
  document.querySelector('[data-testid="profile-greeting"]').textContent = 'Hello, ' + username + '!';
  document.getElementById('profile').hidden = false;
}}
function showLogin() {{
  localStorage.removeItem('demo_token');
  document.getElementById('profile').hidden = true;
  document.getElementById('login-form-wrap').hidden = false;
}}
document.getElementById('login-btn').addEventListener('click', async function () {{
  var username = document.getElementById('username').value;
  var password = document.getElementById('password').value;
  var err = document.getElementById('login-error');
  err.hidden = true;
  try {{
    var res = await fetch('/api/login', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{username: username, password: password}})
    }});
    var data = await res.json();
    if (!res.ok) {{ err.textContent = data.error || 'Login failed.'; err.hidden = false; return; }}
    localStorage.setItem('demo_token', data.token);
    showProfile(data.username);
  }} catch (e) {{ err.textContent = 'Login request failed.'; err.hidden = false; }}
}});
document.getElementById('logout-btn').addEventListener('click', showLogin);
(function () {{
  var token = localStorage.getItem('demo_token');
  if (token === '{DEMO_TOKEN}') showProfile('{DEMO_USERNAME}');
}})();
</script>
<footer data-testid="page-footer">Demo App footer - automation friendly</footer>
</body></html>
"""

USERS_HTML = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Demo App - Users</title>{_BASE_STYLE}</head>
<body>
{_NAV}
<h1>Users</h1>
<label for="search">Search users</label>
<input id="search" data-testid="input-user-search" type="text" autocomplete="off">
<button id="refresh" data-testid="btn-refresh-users">Refresh</button>
<div id="users-empty" data-testid="users-empty" hidden>No users found.</div>
<table data-testid="users-table">
  <thead><tr><th>ID</th><th>Name</th><th>Username</th><th>Email</th><th>Role</th></tr></thead>
  <tbody id="users-body"></tbody>
</table>
<script>
async function loadUsers() {{
  var res = await fetch('/api/users');
  var users = await res.json();
  render(users);
}}
function render(users) {{
  var q = document.getElementById('search').value.toLowerCase();
  var body = document.getElementById('users-body');
  var empty = document.getElementById('users-empty');
  body.innerHTML = '';
  var shown = 0;
  users.forEach(function (u) {{
    if (q && (u.name + ' ' + u.username + ' ' + u.email).toLowerCase().indexOf(q) === -1) return;
    shown++;
    var tr = document.createElement('tr');
    tr.setAttribute('data-testid', 'user-row');
    tr.innerHTML = '<td>' + u.id + '</td><td>' + u.name + '</td><td>' + u.username
      + '</td><td>' + u.email + '</td><td>' + u.role + '</td>';
    body.appendChild(tr);
  }});
  empty.hidden = shown !== 0;
}}
document.getElementById('refresh').addEventListener('click', loadUsers);
document.getElementById('search').addEventListener('input', loadUsers);
loadUsers();
</script>
<footer data-testid="page-footer">Demo App footer - automation friendly</footer>
</body></html>
"""


# ------------------------------------------------------------- server control
_servers: dict[int, Any] = {}
_servers_lock = threading.Lock()


def is_demo_app_healthy(url: str, timeout: float = 2.0) -> bool:
    try:
        import requests

        response = requests.get(f"{url.rstrip('/')}/api/health", timeout=timeout)
        return response.ok and response.json().get("app") == "demo-app"
    except Exception:
        return False


def ensure_demo_app_running(host: str = "127.0.0.1", port: int = 8765,
                            max_probe_ports: int = 20,
                            prefer_own: bool = False) -> dict[str, Any]:
    """Ensure the demo app is serving; start it in a thread if needed.

    Args:
        host: Interface to bind / probe.
        port: Preferred port (``0`` = let the OS pick a free port).
        max_probe_ports: How many fallback ports to try after *port*.
        prefer_own: When True, always start a private server instead of
            reusing an already-running one (used by pytest-xdist workers so
            each worker gets an isolated data store).

    Returns:
        ``{"base_url": ..., "api_base_url": ..., "port": ..., "started_here": bool}``

    Safe under concurrent calls (pytest-xdist workers / parallel processes).
    NOTE: Werkzeug's ``make_server`` converts ``EADDRINUSE`` into
    ``SystemExit`` (not ``OSError``), so both are caught and treated as
    "port taken, try the next candidate".
    """
    from werkzeug.serving import make_server

    if port:
        candidates = [port] + [port + i for i in range(1, max_probe_ports + 1)]
    else:
        candidates = [0]  # 0 = OS picks a free port

    if not prefer_own:
        for candidate in candidates:
            url = f"http://{host}:{candidate}"
            if candidate and is_demo_app_healthy(url):
                return {"base_url": url, "api_base_url": f"{url}/api",
                        "port": candidate, "started_here": False}
    for candidate in candidates:
        with _servers_lock:
            if candidate in _servers and not prefer_own:
                url = f"http://{host}:{candidate}"
                if is_demo_app_healthy(url):
                    return {"base_url": url, "api_base_url": f"{url}/api",
                            "port": candidate, "started_here": False}
                continue
            if candidate in _servers and prefer_own:
                continue
            try:
                app = create_app()
                # Silence werkzeug's "Address already in use" stderr chatter
                # while probing contended ports.
                with contextlib.redirect_stderr(io.StringIO()):
                    server = make_server(host, candidate, app, threaded=True)
                actual_port = server.server_port
            except (OSError, SystemExit):
                # Port taken -> before moving on, re-probe: the bind winner
                # may now be healthy and reusable (unless we want our own).
                if not prefer_own:
                    url = f"http://{host}:{candidate}"
                    for _ in range(30):
                        if is_demo_app_healthy(url):
                            return {"base_url": url,
                                    "api_base_url": f"{url}/api",
                                    "port": candidate, "started_here": False}
                        time.sleep(0.1)
                continue
            thread = threading.Thread(target=server.serve_forever, daemon=True,
                                      name=f"demo-app-{actual_port}")
            thread.start()
            _servers[actual_port] = server
        url = f"http://{host}:{actual_port}"
        for _ in range(50):
            if is_demo_app_healthy(url):
                return {"base_url": url, "api_base_url": f"{url}/api",
                        "port": actual_port, "started_here": True}
            time.sleep(0.1)
    raise RuntimeError("Could not start or reach the demo application")


def main() -> None:  # pragma: no cover - manual entry point
    import argparse

    parser = argparse.ArgumentParser(description="Run the bundled demo application")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    info = ensure_demo_app_running(args.host, args.port)
    print(f"Demo app running at {info['base_url']} (api: {info['api_base_url']})")
    print("Press Ctrl+C to stop.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
