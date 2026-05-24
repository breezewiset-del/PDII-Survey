import csv
import secrets
import html
import io
import os
import sqlite3
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse


APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "survey_pulse.db"
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT") or os.environ.get("SURVEY_PORT", "8010"))
ADMIN_USER = "UserAdM"
ADMIN_PASSWORD = "1234"
ADMIN_COOKIE = "survey_admin"
ADMIN_TOKEN = secrets.token_urlsafe(24)


DEPARTMENTS = [
    ("N2", 18),
    ("N3", 18),
    ("N4A", 18),
    ("N4B", 11),
    ("N4C", 11),
    ("N5A", 16),
    ("N5B", 14),
    ("N5C", 15),
    ("N6", 18),
]


POSITIONS = [
    "Manager",
    "SV",
    "Staff",
    "Shift leader",
    "Shift Operator",
]


def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS department_target (
            department TEXT PRIMARY KEY,
            target_count INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS department_survey_response (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT NOT NULL,
            position TEXT NOT NULL,
            approval_wait TEXT NOT NULL CHECK(approval_wait IN ('ใช่', 'ไม่ใช่')),
            example_1 TEXT NOT NULL DEFAULT '',
            example_2 TEXT NOT NULL DEFAULT '',
            example_3 TEXT NOT NULL DEFAULT '',
            example_4 TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL CHECK(status IN ('Pending detail', 'Completed')),
            started_at TEXT NOT NULL,
            completed_at TEXT
        );
        """
    )
    for dept, target in DEPARTMENTS:
        conn.execute(
            """
            INSERT INTO department_target(department, target_count)
            VALUES (?, ?)
            ON CONFLICT(department) DO UPDATE SET target_count=excluded.target_count
            """,
            (dept, target),
        )
    conn.execute(
        "DELETE FROM department_target WHERE department NOT IN (%s)"
        % ",".join("?" for _ in DEPARTMENTS),
        [dept for dept, _ in DEPARTMENTS],
    )
    conn.commit()
    conn.close()


def esc(value):
    return html.escape(str(value), quote=True)


def percent(done, total):
    if total <= 0:
        return 0
    return round(done * 100 / total, 1)


def get_progress():
    conn = db()
    rows = conn.execute(
        """
        SELECT
            d.department,
            d.target_count,
            COUNT(r.id) AS completed
        FROM department_target d
        LEFT JOIN department_survey_response r
            ON r.department = d.department AND r.status = 'Completed'
        GROUP BY d.department, d.target_count
        ORDER BY
            CASE d.department
                WHEN 'N2' THEN 1
                WHEN 'N3' THEN 2
                WHEN 'N4A' THEN 3
                WHEN 'N4B' THEN 4
                WHEN 'N4C' THEN 5
                WHEN 'N5A' THEN 6
                WHEN 'N5B' THEN 7
                WHEN 'N5C' THEN 8
                WHEN 'N6' THEN 9
                ELSE 10
            END
        """
    ).fetchall()
    total_target = sum(row["target_count"] for row in rows)
    total_completed = sum(row["completed"] for row in rows)
    conn.close()
    return rows, total_completed, total_target


def dept_options(selected=""):
    return "".join(
        f'<option value="{esc(dept)}" {"selected" if dept == selected else ""}>{esc(dept)}</option>'
        for dept, _ in DEPARTMENTS
    )


def position_options(selected=""):
    return "".join(
        f'<option value="{esc(position)}" {"selected" if position == selected else ""}>{esc(position)}</option>'
        for position in POSITIONS
    )


def button_group(name, values, selected=""):
    buttons = []
    for value in values:
        active = " active" if value == selected else ""
        buttons.append(
            f'<button class="pick-button{active}" type="submit" name="{esc(name)}" value="{esc(value)}">{esc(value)}</button>'
        )
    return '<div class="button-grid">' + "".join(buttons) + "</div>"


def progress_panel(selected_dept=""):
    rows, total_completed, total_target = get_progress()
    overall = percent(total_completed, total_target)
    bars = []
    for row in rows:
        pct = percent(row["completed"], row["target_count"])
        width = min(pct, 100)
        selected = " selected" if row["department"] == selected_dept else ""
        bars.append(
            f"""
            <article class="progress-row{selected}">
              <div class="progress-meta">
                <strong>{esc(row['department'])}</strong>
                <span>{row['completed']} / {row['target_count']} คน</span>
              </div>
              <div class="bar" aria-label="{esc(row['department'])} {pct}%">
                <span style="width:{width}%"></span>
              </div>
              <b>{pct}%</b>
            </article>
            """
        )
    return f"""
    <aside class="progress-card">
      <div class="progress-card-head">
        <div>
          <p class="eyebrow">Live Participation</p>
          <h2>ความคืบหน้าของแต่ละแผนก</h2>
        </div>
        <div class="ring" style="--pct:{overall}">
          <strong>{overall}%</strong>
          <span>รวม</span>
        </div>
      </div>
      <div class="progress-list">{''.join(bars)}</div>
    </aside>
    """


BASE_CSS = """
:root {
  --ink: #111827;
  --muted: #6b7280;
  --line: #e5e7eb;
  --panel: rgba(255,255,255,.96);
  --bg: #050816;
  --accent: #4f46e5;
  --accent-2: #06b6d4;
  --accent-3: #a855f7;
  --navy: #090d1f;
  --danger: #b42318;
  --shadow: 0 28px 80px rgba(2,6,23,.24);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  font-family: "Segoe UI", Tahoma, Arial, sans-serif;
  color: var(--ink);
  background:
    radial-gradient(circle at 14% 12%, rgba(79,70,229,.34), transparent 26rem),
    radial-gradient(circle at 85% 14%, rgba(6,182,212,.24), transparent 24rem),
    radial-gradient(circle at 55% 92%, rgba(168,85,247,.18), transparent 28rem),
    linear-gradient(135deg, #050816 0%, #0a1024 48%, #111827 100%);
}
a { color: inherit; }
.shell {
  width: min(1180px, calc(100% - 32px));
  margin: 0 auto;
  padding: 28px 0;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 900;
  letter-spacing: .2px;
  color: #fff;
}
.brand-mark {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: white;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  box-shadow: 0 10px 28px rgba(79,70,229,.38);
}
.top-link {
  text-decoration: none;
  color: rgba(255,255,255,.78);
  font-weight: 700;
  font-size: 14px;
}
.hero {
  min-height: calc(100vh - 88px);
  display: grid;
  grid-template-columns: minmax(320px, 1fr) 420px;
  gap: 24px;
  align-items: center;
}
.hero-panel, .form-card, .progress-card, .thanks-card, .admin-panel {
  background: var(--panel);
  border: 1px solid rgba(255,255,255,.16);
  border-radius: 8px;
  box-shadow: var(--shadow);
  backdrop-filter: blur(12px);
}
.hero-panel {
  color: #fff;
  padding: clamp(28px, 5vw, 58px);
  overflow: hidden;
  position: relative;
  min-height: 620px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background:
    linear-gradient(140deg, rgba(255,255,255,.10), rgba(255,255,255,.03)),
    linear-gradient(135deg, #090d1f, #151a33 58%, #2d1b69);
  border-color: rgba(255,255,255,.14);
}
.hero-panel:before {
  content: "";
  position: absolute;
  inset: 0 0 auto auto;
  width: 360px;
  height: 360px;
  background: radial-gradient(circle, rgba(6,182,212,.26), transparent 62%);
  pointer-events: none;
}
.hero-panel:after {
  content: "";
  position: absolute;
  inset: auto -80px -90px auto;
  width: 380px;
  height: 240px;
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 8px;
  transform: rotate(-8deg);
  background: linear-gradient(135deg, rgba(79,70,229,.20), rgba(6,182,212,.12));
  pointer-events: none;
}
.eyebrow {
  margin: 0 0 10px;
  color: var(--accent-2);
  text-transform: uppercase;
  letter-spacing: .08em;
  font-size: 12px;
  font-weight: 900;
}
h1 {
  margin: 0;
  font-size: clamp(36px, 6vw, 68px);
  line-height: .95;
  letter-spacing: 0;
}
h2 { margin: 0; font-size: clamp(22px, 3vw, 34px); line-height: 1.08; }
p { line-height: 1.7; }
.lead {
  margin: 20px 0 0;
  color: rgba(255,255,255,.82);
  font-size: clamp(17px, 2vw, 22px);
  max-width: 720px;
}
.copy-block {
  margin-top: 24px;
  display: grid;
  gap: 10px;
  color: rgba(255,255,255,.70);
  font-size: 16px;
}
.survey-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 24px 0 0;
}
.survey-chips span {
  border: 1px solid rgba(255,255,255,.14);
  border-radius: 999px;
  padding: 8px 11px;
  color: rgba(255,255,255,.78);
  background: rgba(255,255,255,.08);
  font-size: 13px;
  font-weight: 750;
}
.cta-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 30px;
}
.button, button {
  border: 0;
  border-radius: 8px;
  padding: 13px 18px;
  min-height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  color: white;
  font-weight: 900;
  text-decoration: none;
  cursor: pointer;
  box-shadow: 0 16px 36px rgba(79,70,229,.34);
  font: inherit;
}
.button:hover, button:hover { filter: brightness(1.07); }
.button.secondary {
  color: var(--ink);
  background: white;
  border: 1px solid var(--line);
  box-shadow: none;
}
.survey-layout {
  display: grid;
  grid-template-columns: minmax(320px, 1fr) 420px;
  gap: 22px;
  align-items: start;
}
.form-card { padding: clamp(20px, 3vw, 34px); }
.form-title { margin-bottom: 20px; }
label.field-label {
  display: block;
  margin: 16px 0 7px;
  font-size: 13px;
  font-weight: 850;
  color: #344054;
}
select, textarea, input[type="text"] {
  width: 100%;
  border: 1px solid #c7d0dd;
  border-radius: 8px;
  padding: 12px 13px;
  font: inherit;
  background: white;
}
textarea { min-height: 92px; resize: vertical; }
select:focus, textarea:focus, input:focus {
  outline: 3px solid rgba(15,118,110,.16);
  border-color: var(--accent);
}
.field-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.question-card {
  margin-top: 20px;
  padding: 18px;
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  background: #fbfdff;
}
.question-card h3 {
  margin: 0 0 8px;
  font-size: clamp(20px, 2.5vw, 28px);
  line-height: 1.22;
}
.hint {
  margin: 0;
  color: var(--muted);
  font-size: 14px;
}
.choice-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 18px;
}
.button-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
  gap: 10px;
  margin-top: 8px;
}
.pick-button {
  width: 100%;
  min-height: 48px;
  border: 1px solid #c7d0dd;
  border-radius: 8px;
  background: #fff;
  color: var(--ink);
  box-shadow: none;
  font-weight: 900;
}
.pick-button.active {
  color: #fff;
  border-color: var(--accent);
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  box-shadow: 0 12px 28px rgba(79,70,229,.22);
}
.answer-button {
  min-height: 78px;
  font-size: 24px;
}
.progress-card {
  padding: 20px;
  position: sticky;
  top: 18px;
  background:
    linear-gradient(180deg, rgba(255,255,255,.98), rgba(248,250,252,.96));
}
.progress-card-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 16px;
}
.ring {
  --angle: calc(var(--pct) * 3.6deg);
  width: 98px;
  aspect-ratio: 1;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: conic-gradient(var(--accent-2) var(--angle), #e6edf4 0deg);
  position: relative;
  flex: 0 0 auto;
}
.ring:before {
  content: "";
  position: absolute;
  inset: 10px;
  background: white;
  border-radius: 50%;
}
.ring strong, .ring span { position: relative; }
.ring strong { font-size: 22px; }
.ring span { position: absolute; top: 58px; color: var(--muted); font-size: 11px; }
.progress-list { display: grid; gap: 10px; }
.progress-row {
  display: grid;
  grid-template-columns: 1fr 54px;
  gap: 7px 10px;
  padding: 11px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fbfdff;
}
.progress-row.selected {
  border-color: rgba(245,158,11,.85);
  box-shadow: 0 0 0 4px rgba(245,158,11,.16);
}
.progress-meta {
  grid-column: 1 / -1;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--muted);
  font-size: 13px;
}
.progress-meta strong { color: var(--ink); }
.bar {
  height: 13px;
  border-radius: 999px;
  background: #e6edf4;
  overflow: hidden;
}
.bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--accent), var(--accent-2), var(--accent-3));
}
.progress-row b {
  text-align: right;
  color: var(--accent);
}
.example-grid {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}
.thanks {
  min-height: calc(100vh - 88px);
  display: grid;
  place-items: center;
}
.thanks-card {
  width: min(760px, 100%);
  padding: clamp(28px, 5vw, 54px);
  text-align: center;
}
.check {
  width: 74px;
  height: 74px;
  margin: 0 auto 22px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: white;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  font-size: 38px;
  font-weight: 950;
}
.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.kpi {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}
.kpi > div, .admin-panel {
  background: white;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 16px;
}
.kpi strong { display: block; font-size: 30px; }
.admin-panel { overflow: auto; margin-bottom: 14px; box-shadow: none; }
table { width: 100%; border-collapse: collapse; background: white; }
th, td { padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: left; vertical-align: top; font-size: 14px; }
th { background: #eef2f7; }
.toast {
  margin-bottom: 14px;
  padding: 12px 13px;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: var(--danger);
  background: #fef2f2;
  font-weight: 800;
}
.login-wrap {
  min-height: calc(100vh - 88px);
  display: grid;
  place-items: center;
}
.login-card {
  width: min(440px, 100%);
  background: rgba(255,255,255,.96);
  border: 1px solid rgba(255,255,255,.16);
  border-radius: 8px;
  box-shadow: var(--shadow);
  padding: 28px;
}
@media (max-width: 920px) {
  .hero, .survey-layout { grid-template-columns: 1fr; }
  .progress-card { position: static; }
}
@media (max-width: 560px) {
  .shell { width: min(100% - 22px, 1180px); padding: 14px 0; }
  .field-grid, .choice-grid { grid-template-columns: 1fr; }
  .hero-panel, .form-card, .progress-card, .thanks-card { padding: 20px; }
  .topbar { align-items: flex-start; }
}
"""


def layout(content, title="Production II KPP Department Survey"):
    return f"""<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>{BASE_CSS}</style>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <div class="brand"><span class="brand-mark">II</span><span>Production II KPP</span></div>
      <a class="top-link" href="/admin">Admin</a>
    </header>
    {content}
  </div>
</body>
</html>"""


def landing_page():
    content = """
    <main class="hero">
      <section class="hero-panel">
        <p class="eyebrow">Department Survey</p>
        <h1>Production II KPP Department Survey</h1>
        <p class="lead">แบบสอบถามเพื่อการปรับปรุง Department</p>
        <div class="copy-block">
          <p>คำตอบของท่านจะไม่ระบุตัวตน และจะถูกนำไปใช้เพื่อพัฒนาการทำงานให้ดีขึ้น</p>
          <p>ขอความร่วมมือทุกท่านตอบตามความเป็นจริงจากประสบการณ์ในการทำงานของท่าน</p>
          <p><strong>ใช้เวลาไม่เกิน 5 นาที</strong></p>
        </div>
        <div class="survey-chips">
          <span>No login</span>
          <span>Anonymous</span>
          <span>5 minutes</span>
          <span>Live progress</span>
        </div>
        <div class="cta-row">
          <a class="button" href="/survey">เข้าแบบสอบถาม</a>
        </div>
      </section>
      {progress}
    </main>
    """.replace("{progress}", progress_panel())
    return layout(content)


def survey_page(msg="", selected_dept="", selected_position=""):
    message = f'<div class="toast">{esc(msg)}</div>' if msg else ""
    content = f"""
    <main class="survey-layout">
      <section class="form-card">
        <div class="form-title">
          <p class="eyebrow">Step 1 of 2</p>
          <h2>ตอบจากประสบการณ์ทำงานจริงของท่าน</h2>
        </div>
        {message}
        <form method="get" action="/survey">
          <label class="field-label">เลือกแผนก</label>
          {button_group("department", [dept for dept, _ in DEPARTMENTS], selected_dept)}
        </form>
        <form method="get" action="/survey">
          <input type="hidden" name="department" value="{esc(selected_dept)}">
          <label class="field-label">เลือกตำแหน่ง</label>
          {button_group("position", POSITIONS, selected_position)}
        </form>
        <form method="post" action="/survey">
          <input type="hidden" name="department" id="departmentField" value="{esc(selected_dept)}">
          <input type="hidden" name="position" id="positionField" value="{esc(selected_position)}">
          <section class="question-card">
            <h3>งานประจำวันของท่านมีขั้นตอนรออนุมัติเยอะเกินไปไหม ?</h3>
            <p class="hint">(ขั้นตอนซ้ำ เยอะ หรือ ช้าจนมีผลกระทบต่องาน)</p>
            <div class="choice-grid">
              <button class="answer-button" type="submit" name="approval_wait" value="ใช่">ใช่</button>
              <button class="answer-button" type="submit" name="approval_wait" value="ไม่ใช่">ไม่ใช่</button>
            </div>
          </section>
        </form>
        <script>
          const params = new URLSearchParams(location.search);
          document.querySelectorAll('.pick-button[name="department"]').forEach((button) => {{
            if (button.value === "{esc(selected_dept)}") button.classList.add("active");
          }});
        </script>
      </section>
      {progress_panel(selected_dept)}
    </main>
    """
    return layout(content, "Survey")


def detail_page(response_id, msg=""):
    conn = db()
    row = conn.execute(
        "SELECT * FROM department_survey_response WHERE id=? AND status='Pending detail'",
        (response_id,),
    ).fetchone()
    conn.close()
    if not row:
        return thanks_page()
    message = f'<div class="toast">{esc(msg)}</div>' if msg else ""
    content = f"""
    <main class="survey-layout">
      <section class="form-card">
        <div class="form-title">
          <p class="eyebrow">Step 2 of 2</p>
          <h2>ยกตัวอย่างงานของท่าน ที่ขั้นตอนเยอะ ซับซ้อน</h2>
          <p class="hint">กรอกเท่าที่นึกออก ไม่จำเป็นต้องครบทั้ง 4 ช่อง</p>
        </div>
        {message}
        <form method="post" action="/details">
          <input type="hidden" name="id" value="{row['id']}">
          <div class="example-grid">
            <textarea name="example_1" placeholder="ตัวอย่างที่ 1"></textarea>
            <textarea name="example_2" placeholder="ตัวอย่างที่ 2"></textarea>
            <textarea name="example_3" placeholder="ตัวอย่างที่ 3"></textarea>
            <textarea name="example_4" placeholder="ตัวอย่างที่ 4"></textarea>
          </div>
          <button type="submit">ส่งแบบสอบถาม</button>
        </form>
      </section>
      {progress_panel(row['department'])}
    </main>
    """
    return layout(content, "Survey Detail")


def thanks_page():
    content = """
    <main class="thanks">
      <section class="thanks-card">
        <div class="check">✓</div>
        <p class="eyebrow">Completed</p>
        <h1>ขอบคุณสำหรับคำตอบของท่าน</h1>
        <p class="lead">ทุกความคิดเห็นช่วยให้ Production II KPP มองเห็นขั้นตอนที่ควรปรับปรุง และพัฒนาการทำงานให้ลื่นขึ้นสำหรับทุกคน</p>
        <div class="cta-row" style="justify-content:center">
          <a class="button" href="/">กลับหน้าแรก</a>
          <a class="button secondary" href="/survey">ตอบอีกครั้ง</a>
        </div>
      </section>
    </main>
    """
    return layout(content, "Thank You")


def admin_login_page(msg=""):
    message = f'<div class="toast">{esc(msg)}</div>' if msg else ""
    content = f"""
    <main class="login-wrap">
      <section class="login-card">
        <p class="eyebrow">Admin Login</p>
        <h2>Survey Admin</h2>
        <p class="hint">เข้าสู่ระบบเพื่อดูคำตอบและดาวน์โหลด CSV</p>
        {message}
        <form method="post" action="/admin/login">
          <label class="field-label">User</label>
          <input type="text" name="username" autocomplete="off" required>
          <label class="field-label">Password</label>
          <input type="text" name="password" autocomplete="off" required>
          <button type="submit">Log in</button>
        </form>
      </section>
    </main>
    """
    return layout(content, "Admin Login")


def admin_page():
    progress_rows, total_completed, total_target = get_progress()
    conn = db()
    responses = conn.execute(
        """
        SELECT id, department, position, approval_wait, example_1, example_2,
               example_3, example_4, status, started_at, completed_at
        FROM department_survey_response
        ORDER BY id DESC
        """
    ).fetchall()
    by_position = conn.execute(
        """
        SELECT department, position, approval_wait, COUNT(*) AS total
        FROM department_survey_response
        WHERE status='Completed'
        GROUP BY department, position, approval_wait
        ORDER BY department, position, approval_wait
        """
    ).fetchall()
    conn.close()
    overall = percent(total_completed, total_target)
    progress_table = "".join(
        f"<tr><td>{esc(r['department'])}</td><td>{r['completed']}</td><td>{r['target_count']}</td><td>{percent(r['completed'], r['target_count'])}%</td></tr>"
        for r in progress_rows
    )
    position_table = "".join(
        f"<tr><td>{esc(r['department'])}</td><td>{esc(r['position'])}</td><td>{esc(r['approval_wait'])}</td><td>{r['total']}</td></tr>"
        for r in by_position
    )
    response_table = "".join(
        f"<tr><td>{r['id']}</td><td>{esc(r['department'])}</td><td>{esc(r['position'])}</td>"
        f"<td>{esc(r['approval_wait'])}</td><td>{esc(r['example_1'])}</td><td>{esc(r['example_2'])}</td>"
        f"<td>{esc(r['example_3'])}</td><td>{esc(r['example_4'])}</td><td>{esc(r['status'])}</td><td>{esc(r['completed_at'] or '')}</td></tr>"
        for r in responses
    )
    content = f"""
    <main>
      <div class="admin-header">
        <div>
          <p class="eyebrow">Admin</p>
          <h2>Survey Responses</h2>
        </div>
        <div class="cta-row" style="margin:0">
          <a class="button secondary" href="/">Open Survey</a>
          <a class="button" href="/admin/export.csv">Download CSV</a>
          <a class="button secondary" href="/admin/logout">Log out</a>
        </div>
      </div>
      <section class="kpi">
        <div><strong>{total_completed}</strong><span>Completed</span></div>
        <div><strong>{total_target}</strong><span>Target people</span></div>
        <div><strong>{overall}%</strong><span>Overall progress</span></div>
      </section>
      <section class="admin-panel">
        <h2>Department Progress</h2>
        <table><thead><tr><th>Department</th><th>Completed</th><th>Target</th><th>%</th></tr></thead><tbody>{progress_table}</tbody></table>
      </section>
      <section class="admin-panel">
        <h2>Summary by Position</h2>
        <table><thead><tr><th>Department</th><th>Position</th><th>Answer</th><th>Total</th></tr></thead><tbody>{position_table or '<tr><td colspan="4">No data</td></tr>'}</tbody></table>
      </section>
      <section class="admin-panel">
        <h2>All Responses</h2>
        <table><thead><tr><th>ID</th><th>Department</th><th>Position</th><th>Answer</th><th>Example 1</th><th>Example 2</th><th>Example 3</th><th>Example 4</th><th>Status</th><th>Completed</th></tr></thead><tbody>{response_table or '<tr><td colspan="10">No data</td></tr>'}</tbody></table>
      </section>
    </main>
    """
    return layout(content, "Admin")


def export_csv():
    conn = db()
    rows = conn.execute(
        """
        SELECT id, department, position, approval_wait, example_1, example_2,
               example_3, example_4, status, started_at, completed_at
        FROM department_survey_response
        ORDER BY id DESC
        """
    ).fetchall()
    conn.close()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "id",
            "department",
            "position",
            "approval_wait",
            "example_1",
            "example_2",
            "example_3",
            "example_4",
            "status",
            "started_at",
            "completed_at",
        ]
    )
    for row in rows:
        writer.writerow([row[key] for key in row.keys()])
    return out.getvalue()


class Handler(BaseHTTPRequestHandler):
    def send_html(self, content, status=HTTPStatus.OK):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_csv(self, content):
        data = ("\ufeff" + content).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="department_survey_responses.csv"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def is_admin(self):
        cookie = self.headers.get("Cookie", "")
        return f"{ADMIN_COOKIE}={ADMIN_TOKEN}" in cookie

    def set_admin_cookie_and_redirect(self):
        self.send_response(303)
        self.send_header("Location", "/admin")
        self.send_header(
            "Set-Cookie",
            f"{ADMIN_COOKIE}={ADMIN_TOKEN}; Path=/; HttpOnly; SameSite=Lax",
        )
        self.end_headers()

    def clear_admin_cookie_and_redirect(self):
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header(
            "Set-Cookie",
            f"{ADMIN_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax",
        )
        self.end_headers()

    def redirect(self, path):
        self.send_response(303)
        self.send_header("Location", path)
        self.end_headers()

    def read_form(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        return {key: values[0] for key, values in parse_qs(body).items()}

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if parsed.path == "/":
            self.send_html(landing_page())
        elif parsed.path == "/survey":
            self.send_html(
                survey_page(
                    selected_dept=params.get("department", [""])[0],
                    selected_position=params.get("position", [""])[0],
                )
            )
        elif parsed.path == "/details":
            response_id = params.get("id", [""])[0]
            self.send_html(detail_page(response_id))
        elif parsed.path == "/thanks":
            self.send_html(thanks_page())
        elif parsed.path == "/admin":
            if self.is_admin():
                self.send_html(admin_page())
            else:
                self.send_html(admin_login_page())
        elif parsed.path == "/admin/export.csv":
            if self.is_admin():
                self.send_csv(export_csv())
            else:
                self.send_html(admin_login_page("กรุณา log in ก่อนดาวน์โหลดข้อมูล"), HTTPStatus.UNAUTHORIZED)
        elif parsed.path == "/admin/logout":
            self.clear_admin_cookie_and_redirect()
        else:
            self.send_html(layout("<main class='form-card'><h2>Page not found</h2></main>"), HTTPStatus.NOT_FOUND)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/survey":
                self.submit_survey()
            elif path == "/details":
                self.submit_details()
            elif path == "/admin/login":
                self.admin_login()
            else:
                self.send_html(layout("<main class='form-card'><h2>Page not found</h2></main>"), HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_html(survey_page(str(exc)), HTTPStatus.BAD_REQUEST)

    def submit_survey(self):
        form = self.read_form()
        department = form.get("department", "")
        position = form.get("position", "")
        answer = form.get("approval_wait", "")
        if department not in [dept for dept, _ in DEPARTMENTS]:
            raise ValueError("กรุณาเลือกแผนก")
        if position not in POSITIONS:
            raise ValueError("กรุณาเลือกตำแหน่ง")
        if answer not in ("ใช่", "ไม่ใช่"):
            raise ValueError("กรุณาเลือกคำตอบ")

        conn = db()
        status = "Pending detail" if answer == "ใช่" else "Completed"
        completed_at = None if answer == "ใช่" else now_iso()
        cur = conn.execute(
            """
            INSERT INTO department_survey_response(
                department, position, approval_wait, status, started_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (department, position, answer, status, now_iso(), completed_at),
        )
        response_id = cur.lastrowid
        conn.commit()
        conn.close()

        if answer == "ใช่":
            self.redirect(f"/details?id={response_id}")
        else:
            self.redirect("/thanks")

    def submit_details(self):
        form = self.read_form()
        response_id = form.get("id", "")
        examples = [form.get(f"example_{i}", "").strip() for i in range(1, 5)]
        if not any(examples):
            self.send_html(detail_page(response_id, "กรุณายกตัวอย่างอย่างน้อย 1 ช่อง"), HTTPStatus.BAD_REQUEST)
            return
        conn = db()
        conn.execute(
            """
            UPDATE department_survey_response
            SET example_1=?, example_2=?, example_3=?, example_4=?,
                status='Completed', completed_at=?
            WHERE id=? AND status='Pending detail'
            """,
            (*examples, now_iso(), response_id),
        )
        conn.commit()
        conn.close()
        self.redirect("/thanks")

    def admin_login(self):
        form = self.read_form()
        if form.get("username") == ADMIN_USER and form.get("password") == ADMIN_PASSWORD:
            self.set_admin_cookie_and_redirect()
            return
        self.send_html(admin_login_page("User หรือ Password ไม่ถูกต้อง"), HTTPStatus.UNAUTHORIZED)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Survey Pulse running on http://127.0.0.1:{PORT}")
    print(f"LAN users can open http://<this-pc-ip>:{PORT}")
    server.serve_forever()
