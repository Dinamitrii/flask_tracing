import queue
import shutil
import subprocess
import threading

from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

HTML_PAGE = """
<!doctype html>
<html lang="bg">
<head>
<meta charset="utf-8">
<title>Инструмент за маршрутизиране</title>
<style>
body { font-family: Arial, sans-serif; background: #f5f6fa; padding: 40px; }
h1 { color: #333; text-align: center; }
.container { background: white; padding: 30px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); width: 700px; margin: auto; text-align: center; }
input { padding: 10px; width: 70%; font-size: 16px; border: 1px solid #ccc; border-radius: 8px; }
button { padding: 10px 20px; font-size: 16px; border: none; color: white; border-radius: 8px; cursor: pointer; margin: 8px; }
.btn-trace { background: #007BFF; }
.btn-trace:hover { background: #0056b3; }
.btn-ip { background: #28a745; }
.btn-ip:hover { background: #1e7e34; }
.btn-ping { background: #ff9800; }
.btn-ping:hover { background: #e65100; }
pre { background: #1e1e1e; color: #00ff88; padding: 15px; border-radius: 10px; margin-top: 20px; font-size: 14px; overflow-x: auto; text-align: left; min-height: 200px; white-space: pre-wrap; }

#planet { 
    width:60px; height:60px; border-radius:50%;
    background: radial-gradient(circle at 30% 30%, #66ff66, #0099ff 70%);
    box-shadow: inset -5px -5px 15px rgba(0,0,0,0.3),
                inset 5px 5px 10px rgba(255,255,255,0.2),
                2px 2px 8px rgba(0,0,0,0.2);
    margin:20px auto; display:none;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.trace-line-0 { color: #ff5555; }
.trace-line-1 { color: #55ff55; }
.trace-line-2 { color: #5555ff; }
.trace-line-3 { color: #ffff55; }
.trace-line-4 { color: #ff55ff; }
.trace-line-5 { color: #55ffff; }
</style>
</head>
<body>
<div class="container">
<h1>🌍 Инструмент за маршрутизиране</h1>
<input type="text" id="target" placeholder="напр. 8.8.8.8 или google.com">
<div>
  <button class="btn-trace" onclick="runCommand('trace')">🛰️ Проследи маршрут</button>
  <button class="btn-ip" onclick="runCommand('iproute')">🚦 Провери маршрут</button>
  <button class="btn-ping" onclick="runCommand('ping')">🧪 Ping</button>
</div>
<div id="planet"></div>
<pre id="result">Въведи адрес и натисни бутон...</pre>
</div>

<script>
async function runCommand(cmd) {
    const target = document.getElementById('target').value.trim();
    const resultBox = document.getElementById('result');
    const planet = document.getElementById('planet');
    if (!target) { resultBox.textContent = "❌ Въведи адрес!"; return; }

    planet.style.display = "block";
    resultBox.innerHTML = "";

    if(cmd === 'trace'){
        const res = await fetch('/trace_async', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target })
        });
        const data = await res.json();
        let colorIndex = 0;
        for(const line of data.result){
            resultBox.innerHTML += `<span class="trace-line-${colorIndex%6}">${line}</span>\n`;
            colorIndex++;
            await new Promise(r => setTimeout(r, 150));
        }
    } else {
        const res = await fetch('/' + cmd, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target })
        });
        const data = await res.json();
        resultBox.textContent = data.result;
    }
    planet.style.display = "none";
}
</script>
</body>
</html>
"""


# --- Helper function ---
def run_command_thread(cmd_list, timeout_sec, result_q):
    try:
        output = subprocess.check_output(cmd_list, stderr=subprocess.STDOUT, text=True, timeout=timeout_sec)
        result_q.put(output)
    except subprocess.TimeoutExpired:
        result_q.put('⚠️ Командата изтече поради timeout.')
    except subprocess.CalledProcessError as e:
        result_q.put(f"❌ Грешка:\n{e.output}")
    except Exception as e:
        result_q.put(f"💥 Неочаквана грешка: {type(e).__name__}: {e}")


@app.route('/')
def index():
    return render_template_string(HTML_PAGE)


# --- IP route get с формат ---
@app.route('/iproute', methods=['POST'])
def ip_route():
    data = request.get_json()
    target = data.get('target', '').strip()
    if not target: return jsonify({'result': '❌ Невалиден адрес!'})
    ip_cmd = shutil.which("ip")
    if not ip_cmd: return jsonify({'result': '⚠️ Командата "ip" не е намерена.'})

    result_q = queue.Queue()
    t = threading.Thread(target=run_command_thread, args=([ip_cmd, "route", "get", target], 60, result_q))
    t.start()
    t.join()
    raw = result_q.get()
    # Форматиране: само via, dev, src
    lines = raw.splitlines()
    formatted = []
    for line in lines:
        parts = line.split()
        display = []
        for i, p in enumerate(parts):
            if p in ("via", "dev", "src") and i + 1 < len(parts):
                display.append(f"{p}: {parts[i + 1]}")
        formatted.append(" | ".join(display) if display else line)
    return jsonify({'result': "\n".join(formatted)})


# --- Ping ---
@app.route('/ping', methods=['POST'])
def ping():
    data = request.get_json()
    target = data.get('target', '').strip()
    if not target: return jsonify({'result': '❌ Невалиден адрес!'})
    ping_cmd = shutil.which("ping")
    if not ping_cmd: return jsonify({'result': '⚠️ ping не е намерен.'})

    result_q = queue.Queue()
    t = threading.Thread(target=run_command_thread, args=([ping_cmd, "-c", "6", target], 30, result_q))
    t.start()
    t.join()
    return jsonify({'result': result_q.get()})


# --- Traceroute async и цветно ---
@app.route('/trace_async', methods=['POST'])
def trace_async():
    data = request.get_json()
    target = data.get('target', '').strip()
    if not target: return jsonify({'result': ['❌ Невалиден адрес!']})
    traceroute_cmd = shutil.which("traceroute")
    if not traceroute_cmd: return jsonify({'result': ['⚠️ traceroute не е инсталиран.']})

    try:
        out = subprocess.check_output([traceroute_cmd, "-m", "15", target], stderr=subprocess.STDOUT, text=True,
                                      timeout=180)
        lines = out.splitlines()
        return jsonify({'result': lines})
    except subprocess.TimeoutExpired:
        return jsonify({'result': ['⚠️ traceroute изтече поради timeout.']})
    except subprocess.CalledProcessError as e:
        return jsonify({'result': [f'❌ traceroute грешка:\n{e.output}']})
    except Exception as e:
        return jsonify({'result': [f'💥 Неочаквана грешка: {type(e).__name__}: {e}']})


if __name__ == '__main__':
    app.run()
