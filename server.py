from flask import Flask, render_template, request, jsonify, session, redirect
import json, os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(24).hex()

BASE        = os.path.dirname(os.path.abspath(__file__))
DATA_FILE   = os.path.join(BASE, 'data.json')
DATABASE_URL = os.environ.get('DATABASE_URL', '')
APP_PASSWORD = os.environ.get('APP_PASSWORD', 'LW2026')  # 本機預設；雲端請在 Railway 設定 APP_PASSWORD

# ── Database ──────────────────────────────────────────────────────────────────

def get_pg():
    import psycopg2, psycopg2.extras
    url = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)

def init_db():
    if not DATABASE_URL:
        return
    conn = get_pg()
    cur  = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS project_data (id INT PRIMARY KEY, data JSONB)")
    cur.execute("SELECT COUNT(*) AS n FROM project_data WHERE id=1")
    if cur.fetchone()['n'] == 0 and os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            seed = json.load(f)
        cur.execute("INSERT INTO project_data (id, data) VALUES (1, %s)",
                    (json.dumps(seed, ensure_ascii=False),))
    conn.commit()
    conn.close()

def load():
    if DATABASE_URL:
        conn = get_pg()
        cur  = conn.cursor()
        cur.execute("SELECT data FROM project_data WHERE id=1")
        row  = cur.fetchone()
        conn.close()
        return dict(row['data']) if row else {}
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save(data):
    if DATABASE_URL:
        conn = get_pg()
        cur  = conn.cursor()
        js   = json.dumps(data, ensure_ascii=False)
        cur.execute(
            "INSERT INTO project_data (id,data) VALUES (1,%s) ON CONFLICT (id) DO UPDATE SET data=%s",
            (js, js))
        conn.commit()
        conn.close()
    else:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# ── Auth ──────────────────────────────────────────────────────────────────────

@app.before_request
def require_login():
    if request.endpoint not in ('login', 'static'):
        if not session.get('ok'):
            return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == APP_PASSWORD:
            session['ok'] = True
            return redirect('/')
        error = '密碼錯誤，請再試一次'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html', data=load())

@app.route('/api/data')
def get_data():
    return jsonify(load())

# ── Milestones ────────────────────────────────────────────────────────────────

@app.route('/api/milestone/<int:mid>/toggle', methods=['POST'])
def toggle_milestone(mid):
    data = load()
    for m in data['milestones']:
        if m['id'] == mid:
            m['done'] = not m['done']
    save(data)
    return jsonify({'ok': True})

@app.route('/api/milestones', methods=['POST'])
def add_milestone():
    data = load()
    m = request.json
    m['id'] = max((x['id'] for x in data['milestones']), default=0) + 1
    m.setdefault('done', False)
    data['milestones'].append(m)
    save(data)
    return jsonify({'ok': True, 'milestone': m})

@app.route('/api/milestones/<int:mid>', methods=['PUT'])
def update_milestone(mid):
    data = load()
    for m in data['milestones']:
        if m['id'] == mid:
            m.update(request.json)
    save(data)
    return jsonify({'ok': True})

@app.route('/api/milestones/<int:mid>', methods=['DELETE'])
def delete_milestone(mid):
    data = load()
    data['milestones'] = [m for m in data['milestones'] if m['id'] != mid]
    save(data)
    return jsonify({'ok': True})

# ── Videos ────────────────────────────────────────────────────────────────────

@app.route('/api/videos', methods=['POST'])
def add_video():
    data = load()
    v = request.json
    v['id'] = max((x['id'] for x in data['videos']), default=0) + 1
    v.setdefault('status', '企劃中')
    v.setdefault('metrics', {'views': 0, 'likes': 0, 'comments': 0})
    v['created_at'] = datetime.now().strftime('%Y-%m-%d')
    data['videos'].append(v)
    save(data)
    return jsonify({'ok': True, 'video': v})

@app.route('/api/videos/<int:vid>', methods=['PUT'])
def update_video(vid):
    data = load()
    for v in data['videos']:
        if v['id'] == vid:
            v.update(request.json)
    save(data)
    return jsonify({'ok': True})

@app.route('/api/videos/<int:vid>', methods=['DELETE'])
def delete_video(vid):
    data = load()
    data['videos'] = [v for v in data['videos'] if v['id'] != vid]
    save(data)
    return jsonify({'ok': True})

# ── Logs ──────────────────────────────────────────────────────────────────────

@app.route('/api/logs', methods=['POST'])
def add_log():
    data = load()
    log = request.json
    log['id'] = max((l['id'] for l in data['discussion_log']), default=0) + 1
    log['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    data['discussion_log'].insert(0, log)
    save(data)
    return jsonify({'ok': True, 'log': log})

@app.route('/api/logs/<int:lid>', methods=['DELETE'])
def delete_log(lid):
    data = load()
    data['discussion_log'] = [l for l in data['discussion_log'] if l['id'] != lid]
    save(data)
    return jsonify({'ok': True})

# ── Notes ─────────────────────────────────────────────────────────────────────

@app.route('/api/notes', methods=['PUT'])
def update_notes():
    data = load()
    data['notes'] = request.json.get('notes', '')
    save(data)
    return jsonify({'ok': True})

# ── Startup ───────────────────────────────────────────────────────────────────

try:
    init_db()
except Exception as e:
    print(f"DB init skipped: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5566))
    if port == 5566:
        import webbrowser, threading, time
        def _open():
            time.sleep(1.2)
            webbrowser.open(f'http://localhost:{port}')
        threading.Thread(target=_open, daemon=True).start()
        print("✦ Listen Within 專案管理 App 啟動中...")
        print(f"✦ 開啟瀏覽器：http://localhost:{port}")
        print("✦ 關閉請按 Ctrl+C")
    app.run(port=port, host='0.0.0.0', debug=False)
