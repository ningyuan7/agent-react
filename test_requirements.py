"""Requirement-level regression tests using scripted models and local HTTP."""
import io
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from react_agent.runtime import Agent
from react_agent.models import ChatModel
from react_agent.registry import ToolRegistry
from react_agent.protocol import parse_decision
from react_agent.session import SessionStore, new_session
from react_agent.tools import make_registry
from react_agent.demo import demo_model
from react_agent.web_server import make_handler


class RequirementsTests(unittest.TestCase):
    def test_schema_specific_constraints_and_duplicate(self):
        registry = ToolRegistry()
        registry.register('short', 'test', {'text': {'type':'string','maxLength':3}}, ['text'], lambda a,s:a)
        with self.assertRaises(ValueError):
            registry.call('short', {'text':'long'}, new_session())
        with self.assertRaises(ValueError):
            registry.register('short', 'test', {}, [], lambda a,s:a)

    def test_fenced_json(self):
        value = parse_decision('```json\n{"type":"final","thought":"done","answer":"ok"}\n```')
        self.assertEqual(value['answer'], 'ok')

    def test_parse_error_can_recover(self):
        outputs = iter(['invalid', {'type':'final','thought':'corrected','answer':'ok'}])
        state = new_session()
        self.assertEqual(Agent(lambda context:next(outputs)).run(state,'hi'), 'ok')
        self.assertEqual(state['trace'][0]['status'], 'parse_error')

    def test_valid_actions_stop_at_limit(self):
        decision = {'type':'action','thought':'more','tool':'search','arguments':{'query':'Agent'}}
        state = new_session()
        self.assertIn('最大轮次', Agent(lambda context:decision,max_steps=3).run(state,'search'))
        self.assertEqual(len([x for x in state['trace'] if x['status']=='observation']),3)

    def test_tool_followup_uses_previous_result(self):
        state = new_session()
        outputs = iter([{'type':'action','thought':'compute','tool':'calculator','arguments':{'expression':'2+3'}},
                        {'type':'final','thought':'done','answer':'5'}])
        Agent(lambda context:next(outputs)).run(state,'计算 2+3')
        calls = []
        def followup(context):
            calls.append(context)
            self.assertTrue(any('"value": 5' in m['content'] for m in context['messages']))
            if len(calls)==1:
                return {'type':'action','thought':'double previous value','tool':'calculator','arguments':{'expression':'5*2'}}
            return {'type':'final','thought':'done','answer':'10'}
        self.assertEqual(Agent(followup).run(state,'再乘以二'), '10')

    def test_complete_todo(self):
        state = new_session()
        registry = make_registry()
        registry.call('todo',{'action':'add','text':'写周报'},state)
        registry.call('todo',{'action':'complete','id':1},state)
        self.assertTrue(state['todos'][0]['done'])

    def test_http_model_payload(self):
        response = io.BytesIO(json.dumps({'choices':[{'message':{'content':'ok'}}]}).encode())
        with patch.dict(os.environ, {'LLM_API_KEY':'test-only','LLM_BASE_URL':'https://example.test/v1','LLM_MODEL':'test'}):
            with patch('urllib.request.urlopen',return_value=response) as request:
                result = ChatModel()({'tools':make_registry().schemas(),'summary':'历史','todos':[], 'messages':[{'role':'user','content':'hi'}]})
                self.assertEqual(result,'ok')
                sent = request.call_args.args[0]
                self.assertEqual(sent.full_url,'https://example.test/v1/chat/completions')
                payload = json.loads(sent.data)
                self.assertIn('calculator',payload['messages'][0]['content'])
                self.assertEqual(payload['messages'][-1]['content'],'hi')

    def test_http_errors_redact_key(self):
        failure = urllib.error.HTTPError('https://example.test',401,'Unauthorized',{},io.BytesIO(b'test-only'))
        with patch.dict(os.environ, {'LLM_API_KEY':'test-only'}):
            with patch('urllib.request.urlopen',side_effect=failure):
                with self.assertRaises(RuntimeError) as caught:
                    ChatModel()({'tools':[],'summary':'','todos':[], 'messages':[]})
                self.assertIn('401',str(caught.exception))
                self.assertNotIn('test-only',str(caught.exception))

    def test_web_chat_and_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            server = ThreadingHTTPServer(('127.0.0.1',0),make_handler(Agent(demo_model),SessionStore(directory),'demo'))
            thread = threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            base = 'http://127.0.0.1:'+str(server.server_port)
            def post(path, data):
                request = urllib.request.Request(base+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(request) as response:
                    return json.load(response)
            try:
                for path in ['/', '/app.js','/style.css','/api/config']:
                    with urllib.request.urlopen(base+path) as response:
                        self.assertEqual(response.status,200)
                first = post('/api/chat',{'session':'one','input':'查杭州天气并记待办'})
                self.assertEqual(len(first['state']['todos']),1)
                self.assertEqual(post('/api/session',{'session':'two'})['state']['todos'],[])
                self.assertEqual(len(post('/api/session',{'session':'one'})['state']['todos']),1)
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    post('/api/chat',{'session':'one','input':''})
                self.assertEqual(caught.exception.code,400)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
