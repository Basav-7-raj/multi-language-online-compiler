"""
MLOC - Multi-Language Online Compiler
Author  : Final Year Project
Stack   : Flask + SQLite + subprocess
Run     : python app.py  →  open http://localhost:5000
"""

import os, subprocess, tempfile, textwrap, json
from flask import Flask, render_template_string, request, jsonify
import sqlite3

app = Flask(__name__)

# ─────────────────────────────────────────────
#  DB HELPERS (SQLite Setup)
# ─────────────────────────────────────────────
def get_conn():
    return sqlite3.connect("mloc_db.db")

def db_query(sql, args=(), fetchall=True, commit=False):
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Convert MySQL placeholder %s to SQLite placeholder ?
    sql = sql.replace("%s", "?")
    
    cur.execute(sql, args)
    if commit:
        conn.commit()
        result = cur.lastrowid
    else:
        rows = cur.fetchall()
        result = [dict(row) for row in rows] if fetchall else (dict(rows[0]) if rows else None)
    cur.close()
    conn.close()
    return result

# ─────────────────────────────────────────────
#  COMPILER ENGINE
# ─────────────────────────────────────────────
RUNNERS = {
    "python": {
        "ext": ".py",
        "cmd": lambda f: ["python", f],
    },
    "c": {
        "ext": ".c",
        # We find the compiler folder dynamically, and use a list to pass the direct paths!
        "compile": lambda src, exe: [
            os.path.join(os.path.dirname(__file__), "w64devkit", "bin", "gcc.exe"),
            "-B", os.path.join(os.path.dirname(__file__), "w64devkit", "bin") + os.sep,
            src, "-o", exe, "-lm"
        ],
        "cmd":     lambda exe: [exe],
    },
    "java": {
        "ext": ".java",
        # Java class name must match filename; we always name it Main
        "compile": lambda src, _: ["javac", src],
        "cmd":     lambda f: ["java", "-cp", os.path.dirname(f), "Main"],
        "filename": "Main",   # force filename = Main
    },
}

TIMEOUT = 10   # seconds per execution

def run_code(language: str, code: str) -> dict:
    cfg = RUNNERS.get(language)
    if not cfg:
        return {"output": "", "error": "Unsupported language"}

    with tempfile.TemporaryDirectory() as td:
        fname = cfg.get("filename", "solution")
        src   = os.path.join(td, fname + cfg["ext"])
        exe   = os.path.join(td, fname)          # used only for C

        # Java: patch public class name to Main just in case
        if language == "java":
            code = __fix_java_class(code)

        with open(src, "w") as fh:
            fh.write(code)

        # Compile step (C / Java)
        if "compile" in cfg:
            cc = cfg["compile"](src, exe)
            try:
                cp = subprocess.run(
                    cc, capture_output=True, text=True, timeout=TIMEOUT
                )
                if cp.returncode != 0:
                    return {"output": "", "error": cp.stderr.strip()}
            except subprocess.TimeoutExpired:
                return {"output": "", "error": "Compilation timed out."}

        # Run step
        run_cmd = cfg["cmd"](exe if language == "c" else src)
        try:
            rp = subprocess.run(
                run_cmd, capture_output=True, text=True, timeout=TIMEOUT
            )
            return {
                "output": rp.stdout.strip(),
                "error":  rp.stderr.strip()
            }
        except subprocess.TimeoutExpired:
            return {"output": "", "error": f"Execution timed out ({TIMEOUT}s limit)."}
        except FileNotFoundError as e:
            return {"output": "", "error": f"Runtime not found: {e}"}

def __fix_java_class(code: str) -> str:
    """Rename any public class declaration to 'Main' so javac is happy."""
    import re
    return re.sub(r'\bpublic\s+class\s+\w+', 'public class Main', code, count=1)

# ─────────────────────────────────────────────
#  HTML TEMPLATE  (IDE dark theme)
# ─────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MLOC · Multi-Language Online Compiler</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@400;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/dracula.min.css">
<style>
:root{
  --bg:#0d0f17; --panel:#131722; --card:#1a1f2e;
  --border:#252b3b; --accent:#7c6af7; --accent2:#00d4aa;
  --err:#ff6b6b; --warn:#ffd93d; --txt:#c9d1e0; --txt2:#6b7694;
  --radius:12px; --mono:'JetBrains Mono',monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--txt);font-family:'Syne',sans-serif;min-height:100vh;overflow-x:hidden}
/* NAV */
nav{background:var(--panel);border-bottom:1px solid var(--border);padding:14px 28px;display:flex;align-items:center;gap:16px;position:sticky;top:0;z-index:100;backdrop-filter:blur(8px)}
.logo{font-size:1.4rem;font-weight:800;letter-spacing:-0.5px;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.logo span{font-weight:400;opacity:.6}
.lang-btns{display:flex;gap:8px;margin-left:auto}
.lang-btn{background:var(--card);border:1px solid var(--border);color:var(--txt2);border-radius:8px;padding:6px 16px;font-family:var(--mono);font-size:.8rem;cursor:pointer;transition:.2s}
.lang-btn:hover,.lang-btn.active{background:var(--accent);color:#fff;border-color:var(--accent)}
/* LAYOUT */
.main{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:auto 1fr;gap:0;height:calc(100vh - 62px)}
/* TOOLBAR */
.toolbar{grid-column:1/-1;background:var(--panel);border-bottom:1px solid var(--border);padding:10px 20px;display:flex;align-items:center;gap:12px}
.btn-run{background:linear-gradient(135deg,var(--accent),#5a4fcf);border:none;color:#fff;border-radius:8px;padding:8px 22px;font-family:var(--mono);font-size:.85rem;font-weight:600;cursor:pointer;display:flex;align-items:center;gap:8px;transition:.2s}
.btn-run:hover{transform:translateY(-1px);box-shadow:0 4px 20px rgba(124,106,247,.4)}
.btn-run:active{transform:translateY(0)}
.btn-run.loading{opacity:.7;pointer-events:none}
.btn-save{background:var(--card);border:1px solid var(--border);color:var(--txt2);border-radius:8px;padding:8px 18px;font-family:var(--mono);font-size:.8rem;cursor:pointer;transition:.2s}
.btn-save:hover{border-color:var(--accent2);color:var(--accent2)}
.title-input{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:7px 14px;color:var(--txt);font-family:var(--mono);font-size:.8rem;width:200px}
.title-input:focus{outline:none;border-color:var(--accent)}
.status-pill{margin-left:auto;font-family:var(--mono);font-size:.75rem;padding:4px 12px;border-radius:20px;background:var(--card);color:var(--txt2)}
/* EDITOR PANE */
.editor-pane{background:var(--panel);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
.pane-hdr{padding:10px 18px;font-size:.72rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--txt2);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block}
.dot-r{background:#ff5f57}.dot-y{background:#febc2e}.dot-g{background:#28c840}
.CodeMirror{height:100%!important;font-size:.875rem;font-family:var(--mono);background:#0d0f17!important}
.CodeMirror-scroll{height:100%}
/* OUTPUT PANE */
.output-pane{background:var(--panel);display:flex;flex-direction:column;overflow:hidden}
.output-body{flex:1;padding:18px;font-family:var(--mono);font-size:.84rem;line-height:1.7;overflow-y:auto;white-space:pre-wrap;word-break:break-all}
.out-success{color:var(--accent2)}
.out-error{color:var(--err)}
.out-placeholder{color:var(--txt2);font-style:italic}
/* SAVED PANEL */
.saved-panel{position:fixed;right:-320px;top:62px;width:310px;height:calc(100vh - 62px);background:var(--panel);border-left:1px solid var(--border);overflow-y:auto;transition:.3s;z-index:50;padding:16px}
.saved-panel.open{right:0}
.saved-item{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:12px;margin-bottom:10px;cursor:pointer;transition:.2s}
.saved-item:hover{border-color:var(--accent);background:#1e2336}
.saved-item h6{font-size:.8rem;font-weight:700;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.saved-item span{font-size:.7rem;color:var(--txt2);font-family:var(--mono)}
.badge-lang{font-size:.65rem;padding:2px 8px;border-radius:4px;font-family:var(--mono);font-weight:600}
.badge-python{background:#2d4a2d;color:#69c569}
.badge-c{background:#2d3d4a;color:#79b4d4}
.badge-java{background:#4a3d2d;color:#d4a579}
/* TOAST */
.toast-box{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px 24px;font-family:var(--mono);font-size:.8rem;opacity:0;transition:.3s;z-index:200;pointer-events:none}
.toast-box.show{opacity:1}
/* SPINNER */
@keyframes spin{to{transform:rotate(360deg)}}
.spin{animation:spin .7s linear infinite;display:inline-block}
/* SCROLLBAR */
::-webkit-scrollbar{width:6px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
</style>
</head>
<body>

<nav>
  <div class="logo">ML<span>OC</span></div>
  <div style="font-size:.75rem;color:var(--txt2);font-family:var(--mono)">Multi-Language Online Compiler</div>
  <div class="lang-btns">
    <button class="lang-btn active" onclick="setLang('python')" id="btn-python"><i class="fab fa-python"></i> Python</button>
    <button class="lang-btn" onclick="setLang('c')" id="btn-c"><i class="fas fa-copyright"></i> C</button>
    <button class="lang-btn" onclick="setLang('java')" id="btn-java"><i class="fab fa-java"></i> Java</button>
  </div>
  <button class="btn-save" style="margin-left:16px" onclick="toggleSaved()"><i class="fas fa-folder-open"></i> Saved</button>
</nav>

<div class="main">
  <div class="toolbar">
    <input class="title-input" id="titleInput" placeholder="Code title…" value="Untitled">
    <button class="btn-run" id="runBtn" onclick="runCode()">
      <i class="fas fa-play"></i> Run
    </button>
    <button class="btn-save" onclick="saveCode()"><i class="fas fa-save"></i> Save</button>
    <button class="btn-save" onclick="clearEditor()"><i class="fas fa-broom"></i> Clear</button>
    <div class="status-pill" id="statusPill">Ready</div>
  </div>

  <div class="editor-pane">
    <div class="pane-hdr">
      <span class="dot dot-r"></span><span class="dot dot-y"></span><span class="dot dot-g"></span>
      &nbsp; <span id="editorLabel">editor · python</span>
    </div>
    <textarea id="editor"></textarea>
  </div>

  <div class="output-pane">
    <div class="pane-hdr"><i class="fas fa-terminal" style="color:var(--accent2)"></i>&nbsp; output</div>
    <div class="output-body" id="outputBox">
      <span class="out-placeholder">// Hit ▶ Run to execute your code…</span>
    </div>
  </div>
</div>

<div class="saved-panel" id="savedPanel">
  <div style="font-size:.7rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--txt2);margin-bottom:12px"><i class="fas fa-bookmark"></i>&nbsp; Saved Snippets</div>
  <div id="savedList">Loading…</div>
</div>

<div class="toast-box" id="toast"></div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/python/python.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/clike/clike.min.js"></script>

<script>
const STARTERS = {
  python:`# Python starter\ndef greet(name):\n    print(f"Hello, {name}! Welcome to MLOC.")\n\ngreet("World")\nfor i in range(1, 6):\n    print(f"  {i} x {i} = {i*i}")`,
  c:`#include <stdio.h>\n\nint main() {\n    printf("Hello from C!\\n");\n    for(int i=1;i<=5;i++)\n        printf("  %d x %d = %d\\n",i,i,i*i);\n    return 0;\n}`,
  java:`public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello from Java!");\n        for(int i=1;i<=5;i++)\n            System.out.printf("  %d x %d = %d%n",i,i,i*i);\n    }\n}`
};

let lang = 'python';

const editor = CodeMirror.fromTextArea(document.getElementById('editor'), {
  theme:'dracula', lineNumbers:true, indentUnit:4,
  mode:'python', lineWrapping:true, autofocus:true
});
editor.setValue(STARTERS.python);
editor.setSize(null, '100%');

function setLang(l) {
  lang = l;
  document.querySelectorAll('.lang-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('btn-'+l).classList.add('active');
  const modeMap = {python:'python', c:'text/x-csrc', java:'text/x-java'};
  editor.setOption('mode', modeMap[l]);
  editor.setValue(STARTERS[l]);
  document.getElementById('editorLabel').textContent = `editor · ${l}`;
  document.getElementById('outputBox').innerHTML = '<span class="out-placeholder">// Hit ▶ Run to execute your code…</span>';
  document.getElementById('statusPill').textContent = 'Ready';
}

async function runCode() {
  const btn = document.getElementById('runBtn');
  btn.innerHTML = '<i class="fas fa-circle-notch spin"></i> Running…';
  btn.classList.add('loading');
  document.getElementById('statusPill').textContent = 'Executing…';
  document.getElementById('outputBox').innerHTML = '<span class="out-placeholder">Running…</span>';

  try {
    const res  = await fetch('/run', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({language:lang, code:editor.getValue()})
    });
    const data = await res.json();
    const box  = document.getElementById('outputBox');
    if (data.error) {
      box.innerHTML = `<span class="out-error">[ERROR]\n${esc(data.error)}</span>`;
      document.getElementById('statusPill').textContent = '✗ Error';
    } else if (data.output) {
      box.innerHTML = `<span class="out-success">${esc(data.output)}</span>`;
      document.getElementById('statusPill').textContent = '✓ Success';
    } else {
      box.innerHTML = '<span class="out-placeholder">// No output produced.</span>';
      document.getElementById('statusPill').textContent = '✓ Done';
    }
  } catch(e) {
    document.getElementById('outputBox').innerHTML = `<span class="out-error">Network error: ${e}</span>`;
  }

  btn.innerHTML = '<i class="fas fa-play"></i> Run';
  btn.classList.remove('loading');
}

async function saveCode() {
  const payload = {
    title: document.getElementById('titleInput').value || 'Untitled',
    language: lang,
    code: editor.getValue(),
    output: document.getElementById('outputBox').innerText
  };
  const res  = await fetch('/save', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  const data = await res.json();
  toast(data.ok ? '✓ Saved!' : '✗ Save failed');
  if (data.ok) loadSaved();
}

async function loadSaved() {
  const res  = await fetch('/snippets');
  const data = await res.json();
  const list = document.getElementById('savedList');
  if (!data.length) { list.innerHTML = '<span style="color:var(--txt2);font-size:.75rem">No saved snippets yet.</span>'; return; }
  list.innerHTML = data.map(s=>`
    <div class="saved-item" onclick="loadSnippet(${s.id})">
      <h6>${esc(s.title)} <span class="badge-lang badge-${s.language}">${s.language}</span></h6>
      <span>${s.created_at}</span>
    </div>`).join('');
}

async function loadSnippet(id) {
  const res  = await fetch(`/snippets/${id}`);
  const s    = await res.json();
  setLang(s.language);
  editor.setValue(s.code);
  document.getElementById('titleInput').value = s.title;
  toggleSaved();
}

function toggleSaved() {
  const p = document.getElementById('savedPanel');
  p.classList.toggle('open');
  if (p.classList.contains('open')) loadSaved();
}

function clearEditor() { editor.setValue(STARTERS[lang]); document.getElementById('outputBox').innerHTML='<span class="out-placeholder">// Hit ▶ Run to execute your code…</span>'; }

function esc(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'), 2500);
}

// Ctrl+Enter to run
document.addEventListener('keydown', e=>{ if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){ e.preventDefault(); runCode(); }});
</script>
</body>
</html>"""

# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/run", methods=["POST"])
def execute():
    data = request.get_json(force=True)
    lang = data.get("language", "python")
    code = data.get("code", "")
    if not code.strip():
        return jsonify(output="", error="No code provided.")
    result = run_code(lang, code)
    return jsonify(result)

@app.route("/save", methods=["POST"])
def save():
    d = request.get_json(force=True)
    try:
        db_query(
            "INSERT INTO saved_codes (title, language, code, output) VALUES (%s,%s,%s,%s)",
            (d.get("title","Untitled"), d.get("language","python"),
             d.get("code",""), d.get("output","")),
            commit=True
        )
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, error=str(e))

@app.route("/snippets")
def snippets():
    rows = db_query(
        "SELECT id, title, language, DATE_FORMAT(created_at,'%d %b %Y') AS created_at "
        "FROM saved_codes ORDER BY id DESC LIMIT 30"
    )
    return jsonify(rows)

@app.route("/snippets/<int:sid>")
def snippet(sid):
    row = db_query("SELECT * FROM saved_codes WHERE id=%s", (sid,), fetchall=False)
    return jsonify(row)

# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n  ╔══════════════════════════════════════╗")
    print("  ║   MLOC · Multi-Language Compiler     ║")
    print("  ║   http://localhost:5000              ║")
    print("  ╚══════════════════════════════════════╝\n")
    app.run(debug=True, host="0.0.0.0", port=5000)