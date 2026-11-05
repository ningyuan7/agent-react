"""Local browser interface for the existing ReAct runtime."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .demo import demo_model
from .models import ChatModel
from .runtime import Agent
from .session import SessionStore

WEB_ROOT = Path(__file__).resolve().parent.parent / 'web'


def make_handler(agent, store, mode):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, payload, content_type='application/json; charset=utf-8'):
            body = json.dumps(payload, ensure_ascii=False).encode() if isinstance(payload, dict) else payload
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/api/config':
                self.respond(200, {'mode': mode, 'tools': agent.registry.schemas()})
                return
            assets = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
            if path not in assets:
                self.respond(404, {'error': '页面不存在'})
                return
            filename, content_type = assets[path]
            self.respond(200, (WEB_ROOT / filename).read_bytes(), content_type + '; charset=utf-8')

        def do_POST(self):
            if self.headers.get('Origin') and self.headers['Origin'] != 'http://' + self.headers.get('Host', ''):
                self.respond(403, {'error': '不允许跨站请求'})
                return
            if self.path not in ('/api/chat', '/api/session'):
                self.respond(404, {'error': '接口不存在'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 32768:
                    raise ValueError('请求大小无效')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('请求必须是对象')
                session_id = data.get('session')
                if not isinstance(session_id, str) or not 1 <= len(session_id) <= 100:
                    raise ValueError('会话 ID 无效')
                def operation(state):
                    if self.path == '/api/chat':
                        return agent.run(state, data.get('input'))
                _, state = store.transact('A', session_id, operation)
                self.respond(200, {'session': session_id, 'state': state})
            except (ValueError, TypeError) as error:
                self.respond(400, {'error': str(error)})
            except OSError:
                self.respond(409, {'error': '会话正在使用或无法保存，请稍后重试'})
            except Exception:
                self.respond(500, {'error': '服务执行失败，请检查服务端配置'})
    return Handler


def main():
    parser = argparse.ArgumentParser(description='ReAct Agent web interface')
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--data-dir', default='data')
    args = parser.parse_args()
    try:
        model = demo_model if args.demo else ChatModel()
    except ValueError as error:
        parser.error(str(error))
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(
        Agent(model), SessionStore(args.data_dir), '规则演示' if args.demo else '真实模型'))
    print(f'Agent 页面 http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
