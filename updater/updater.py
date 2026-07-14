import os
import sys
import json
import time
import subprocess
import threading
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

TOKEN_FILE = "/tmp/arl_update_token"
LOG_FILE = "/tmp/arl_update.log"
PORT = 8888

update_thread = None
dynamic_progress = {}

class PollingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        
        if parsed_url.path == "/update/trigger":
            self.handle_trigger(parsed_url)
        elif parsed_url.path == "/update/log":
            self.handle_log()
        else:
            self.send_response(404)
            self.end_headers()

    def handle_trigger(self, parsed_url):
        global update_thread, dynamic_progress
        query_params = parse_qs(parsed_url.query)
        token = query_params.get("token", [""])[0]
        
        if not self.verify_token(token):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b'{"status": "error", "message": "Invalid token"}')
            return

        # Invalidate token inside container
        try:
            subprocess.run(["docker", "exec", "arl-web-prod", "rm", "-f", TOKEN_FILE])
        except Exception:
            pass

        # clear log file
        with open(LOG_FILE, 'w') as f:
            f.write("⏳ 正在初始化更新任务...\n")
        
        dynamic_progress.clear()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b'{"status": "ok", "message": "Update triggered"}')

        # Start update in background if not already running
        if update_thread is None or not update_thread.is_alive():
            update_thread = threading.Thread(target=self.run_update_task)
            update_thread.start()

    def handle_log(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
        content = ""
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            content = "Waiting for logs...\n"
            
        for layer, prog in dynamic_progress.items():
            content += f"🔄 {layer}: {prog}\n"
            
        self.wfile.write(content.encode('utf-8'))

    def log_append(self, text):
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(text + "\n")

    def run_update_task(self):
        self.log_append("[INFO] ✅ Token 验证成功，后台任务已启动...")
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "start-prod.sh"))
        
        self.log_append("[INFO] 📦 正在拉取核心镜像以提取最新架构配置...")
        image_name = "crpi-laul1izptqrf0tkf.cn-beijing.personal.cr.aliyuncs.com/owl234-arl-prod/arl-web:latest"
        self.run_command(["docker", "pull", image_name])
        
        self.log_append("[INFO] 📦 正在提取并覆盖最新基础架构文件...")
        cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        copy_cmd = [
            "docker", "run", "--rm",
            "-v", f"{cwd}:/host",
            image_name,
            "bash", "-c",
            "cp /code/start-prod.sh /code/docker-compose.prod.yml /host/ 2>/dev/null || true; cp /code/updater/updater.py /host/updater/ 2>/dev/null || true"
        ]
        self.run_command(copy_cmd)
        
        # 赋予可执行权限
        subprocess.run(["chmod", "+x", script_path])
        
        self.log_append("[INFO] 📦 基础架构同步完毕，正在拉取其余 Docker 镜像并部署...")
        self.log_append("[INFO] 🚀 开始执行 start-prod.sh，这可能需要几分钟...")
        
        success = self.run_command(["bash", script_path])
        if success:
            self.log_append("[DONE] 🎉 系统更新与部署已全部完成！请刷新页面体验新版本。")
        else:
            self.log_append("[ERROR] ❌ 部署脚本执行失败，部分服务异常，请仔细检查上述日志！")
            
        # 让前端有充足的时间（约5秒）通过轮询获取到最后的 [DONE] 或 [ERROR] 日志
        time.sleep(5)
        # 体面地结束整个 Python 进程，触发 Systemd 的 Restart=always 机制拉起新版本
        os._exit(0)

    def run_command(self, cmd):
        global dynamic_progress
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        
        try:
            # We want start-prod.sh not to restart this very python service if possible.
            # We pass an env var to inform start-prod.sh to skip restarting us.
            env = os.environ.copy()
            env["ARL_UPDATER_SKIP_RESTART"] = "1"
            
            cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=cwd,
                env=env
            )
            
            for line in iter(process.stdout.readline, ''):
                line = ansi_escape.sub('', line.strip())
                if not line:
                    continue
                
                if 'Downloading' in line or 'Extracting' in line:
                    parts = line.split(': ', 1)
                    if len(parts) >= 2:
                        dynamic_progress[parts[0]] = parts[1]
                    else:
                        dynamic_progress["_general"] = line
                    continue
                    
                if 'complete' in line.lower():
                    parts = line.split(': ', 1)
                    if len(parts) >= 2 and parts[0] in dynamic_progress:
                        del dynamic_progress[parts[0]]
                        
                self.log_append(line)
                
            process.wait()
            
            if process.returncode != 0:
                self.log_append(f"[ERROR] ⚠️ 脚本执行出错，退出码: {process.returncode}")
                return False
            return True
        except Exception as e:
            self.log_append(f"[ERROR] ❌ 执行异常: {str(e)}")
            return False

    def verify_token(self, provided_token):
        if not provided_token:
            return False
        try:
            result = subprocess.run(["docker", "exec", "arl-web-prod", "cat", TOKEN_FILE], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                valid_token = result.stdout.strip()
                return provided_token == valid_token and len(valid_token) > 10
        except Exception:
            pass
        return False

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), PollingHandler)
    print(f"Update server started on port {PORT}...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
