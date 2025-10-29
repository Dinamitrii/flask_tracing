from flask import Flask, render_template_string, request, jsonify
import subprocess, shutil, re

app = Flask(__name__)

HTML_PAGE = """
<!doctype html>
<html lang="bg">
<head>
  <meta charset="utf-8">
  <title>Проследяване на маршрут</title>
  <style>
    body { font-family: Arial, sans-serif; background: #f5f6fa; padding: 40px; }
    h1 { color: #333; }
    .container { background: white; padding: 30px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); width: 650px; margin: auto; text-align: center; }
    input { padding: 10px; width: 70%; font-size: 16px; border: 1px solid #ccc; border-radius: 8px; }
    button { padding: 10px 20px; font-size: 16px; border: none; color: white; border-radius: 8px; cursor: pointer; margin: 8px; }
    .btn-trace { background: #007BFF; }
    .btn-trace:hover { background: #0056b3; }
    .btn-ip { background: #28a745; }
    .btn-ip:hover { background: #1e7e34; }
    pre { background: #1e1e1e; color: #00ff88; padding: 15px; border-radius: 10px; margin-top: 20px; font-size: 14px; overflow-x: auto; text-align: left; }
  </style>
</head>
<body>
  <div class="container">
    <h1>🌍 Инструмент за маршрутизиране</h1>
    <input type="text" id="target" placeholder="напр. 8.8.8.8 или google.com">
    <div>
      <button class="btn-trace" onclick="runCommand('trace')">🛰️ Проследи маршрут</button>
      <button class="btn-ip" onclick="runCommand('iproute')">🚦 Провери маршрут</button>
    </div>
    <pre id="result">Въведи адрес и натисни бутон...</pre>
  </div>

  <script>
  async function runCommand(cmd) {
    const target = document.getElementById('target').value.trim();
    const resultBox = document.getElementById('result');
    if (!target) {
      resultBox.textContent = "❌ Въведи адрес!";
      return;
    }
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
    }
  }
  </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

# ✅ ip route get
@app.route('/iproute', methods=['POST'])
def ip_route():
    data = request.get_json()
    target = (data.get('target') or '').strip()

    if not re.match(r'^[a-zA-Z0-9.:-]+$', target):
        return jsonify({'result': '❌ Невалиден адрес!'})

    ip_cmd = shutil.which("ip")
    if not ip_cmd:
        return jsonify({'result': '⚠️ Командата "ip" не е намерена в системата.'})

    try:
        out = subprocess.check_output([ip_cmd, "route", "get", target],
                                      stderr=subprocess.STDOUT,
                                      text=True,
                                      timeout=10)
        return jsonify({'result': f"(ip route get)\n{out}"})
    except subprocess.TimeoutExpired:
        return jsonify({'result': '⚠️ Времето за изпълнение изтече (ip route get).'})
    except subprocess.CalledProcessError as e:
        return jsonify({'result': f"❌ Грешка от ip route get:\n{e.output}"})
    except Exception as e:
        return jsonify({'result': f"💥 Неочаквана грешка: {type(e).__name__}: {e}"})


# ✅ traceroute
@app.route('/trace', methods=['POST'])
def traceroute():
    data = request.get_json()
    target = (data.get('target') or '').strip()

    if not re.match(r'^[a-zA-Z0-9.:-]+$', target):
        return jsonify({'result': '❌ Невалиден адрес!'})

    traceroute_cmd = shutil.which("traceroute")
    timeout_cmd = shutil.which("timeout")

    if not traceroute_cmd:
        return jsonify({'result': '⚠️ traceroute не е инсталиран (sudo apt install traceroute)'})

    # опит с timeout, ако има
    try:
        if timeout_cmd:
            cmd = [timeout_cmd, "120", traceroute_cmd, "-m", "15", target]
        else:
            cmd = [traceroute_cmd, "-m", "15", target]

        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=120)
        return jsonify({'result': f"(traceroute)\n{out}"})
    except subprocess.TimeoutExpired:
        return jsonify({'result': '⚠️ traceroute изтече поради timeout.'})
    except subprocess.CalledProcessError as e:
        return jsonify({'result': f"❌ traceroute грешка:\n{e.output}"})
    except Exception as e:
        return jsonify({'result': f"💥 Неочаквана грешка: {type(e).__name__}: {e}"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
