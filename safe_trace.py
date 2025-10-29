from flask import Flask, render_template_string, request, jsonify
import subprocess, shutil, re, threading, queue

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
    pre { background: #1e1e1e; color: #00ff88; padding: 15px; border-radius: 10px; margin-top: 20px; font-size: 14px; overflow-x: auto; text-align: left; min-height: 200px; }

    /* Долна глобус планета */
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
    if (!target) {
      resultBox.textContent = "❌ Въведи адрес!";
      return;
    }

    planet.style.display = "block";  // покажи въртящата се планета
    resultBox.textContent = "⏳ Изпълнява се...";

    try {
      const res = await fetch('/' + cmd, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target })
      });
      const data = await res.json();
      resultBox.textContent = data.result;
    } catch (err) {
      resultBox.textContent = "❌ Грешка при заявката.";
    } finally {
      planet.style.display = "none"; // скрий планетата след завършване
    }
  }
  </script>
</body>
</html>
"""


# --- Helper функция за изпълнение на команди в thread ---
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


# --- Безопасен endpoint за ip route get ---
@app.route('/iproute', methods=['POST'])
def ip_route():
    data = request.get_json()
    target = (data.get('target') or '').strip()
    if not re.match(r'^[a-zA-Z0-9.:-]+$', target):
        return jsonify({'result': '❌ Невалиден адрес!'})

    ip_cmd = shutil.which("ip")
    if not ip_cmd:
        return jsonify({'result': '⚠️ Командата "ip" не е намерена в системата.'})

    result_q = queue.Queue()
    t = threading.Thread(target=run_command_thread, args=([ip_cmd, "route", "get", target], 10, result_q))
    t.start();
    t.join()
    return jsonify({'result': result_q.get()})


# --- Безопасен endpoint за traceroute ---
@app.route('/trace', methods=['POST'])
def traceroute():
    data = request.get_json()
    target = (data.get('target') or '').strip()
    if not re.match(r'^[a-zA-Z0-9.:-]+$', target):
        return jsonify({'result': '❌ Невалиден адрес!'})

    traceroute_cmd = shutil.which("traceroute")
    if not traceroute_cmd:
        return jsonify({'result': '⚠️ traceroute не е инсталиран (sudo apt install traceroute)'})

    result_q = queue.Queue()
    t = threading.Thread(target=run_command_thread, args=([traceroute_cmd, "-m", "10", target], 20, result_q))
    t.start();
    t.join()
    return jsonify({'result': result_q.get()})


# --- Безопасен endpoint за ping ---
@app.route('/ping', methods=['POST'])
def ping():
    data = request.get_json()
    target = (data.get('target') or '').strip()
    if not re.match(r'^[a-zA-Z0-9.:-]+$', target):
        return jsonify({'result': '❌ Невалиден адрес!'})

    ping_cmd = shutil.which("ping")
    if not ping_cmd:
        return jsonify({'result': '⚠️ ping не е намерен (sudo apt install iputils-ping)'})

    result_q = queue.Queue()
    t = threading.Thread(target=run_command_thread, args=([ping_cmd, "-c", "4", target], 15, result_q))
    t.start();
    t.join()
    return jsonify({'result': result_q.get()})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
