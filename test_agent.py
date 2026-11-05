import tempfile
import unittest
from react_agent.runtime import Agent
from react_agent.session import SessionStore, new_session
from react_agent.tools import calculate, make_registry
from react_agent.context import compress
from react_agent.demo import demo_model
from react_agent.protocol import parse_decision


class AgentTests(unittest.TestCase):
    def test_calculator(self):
        self.assertEqual(calculate('(12+8)*3'), 60)
        for expression in ['1/0', '__import__("os")', '2**1000', '(1+2']:
            with self.assertRaises(Exception):
                calculate(expression)

    def test_schema(self):
        registry = make_registry()
        for name, args in [('missing', {}), ('weather', {}), ('weather', {'city': 1}), ('todo', {'action': 'bad'})]:
            with self.assertRaises(ValueError):
                registry.call(name, args, new_session())

    def test_parser(self):
        self.assertEqual(parse_decision('{"type":"final","thought":"done","answer":"hi"}')["answer"], 'hi')
        for raw in ['bad', '{}', '[]']:
            with self.assertRaises(ValueError):
                parse_decision(raw)

    def test_multi_action_and_followups(self):
        state = new_session()
        agent = Agent(demo_model)
        agent.run(state, '查杭州天气并记待办')
        self.assertEqual(len(state['todos']), 1)
        self.assertEqual(len([t for t in state['trace'] if t['status'] == 'observation']), 2)
        self.assertIn('杭州', agent.run(state, '查看待办'))
        self.assertIn('杭州', agent.run(state, '刚才说了什么'))

    def test_direct_reply(self):
        state = new_session()
        self.assertTrue(Agent(demo_model).run(state, '你好'))
        self.assertEqual(len(state['trace']), 1)

    def test_limit(self):
        state = new_session()
        self.assertIn('最大轮次', Agent(lambda context: '{}', max_steps=2).run(state, 'hi'))
        self.assertEqual(len(state['trace']), 2)

    def test_observation_drives_recovery(self):
        outputs = iter([{'type': 'action', 'thought': 'calculate', 'tool': 'calculator', 'arguments': {'expression': '1/0'}},
                        {'type': 'final', 'thought': 'failed', 'answer': '除数不能为零'}])
        def model(context):
            if len(context['messages']) > 1:
                self.assertIn('"ok": false', context['messages'][-1]['content'])
            return next(outputs)
        state = new_session()
        self.assertEqual(Agent(model).run(state, '计算'), '除数不能为零')
        self.assertFalse(state['trace'][1]['ok'])

    def test_model_failure(self):
        def model(context):
            raise TimeoutError('timeout')
        state = new_session()
        self.assertIn('模型请求失败', Agent(model).run(state, 'hi'))

    def test_compression(self):
        state = new_session()
        state['turns'] = [[{'role': 'user', 'content': 'x' * 1000}] for _ in range(40)]
        state['todos'] = [{'text': 'keep'}]
        compress(state)
        self.assertLess(len(state['turns']), 40)
        self.assertLessEqual(len(state['summary']), 4000)
        self.assertEqual(state['todos'][0]['text'], 'keep')

    def test_persistence_user_and_window_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SessionStore(directory)
            agent = Agent(demo_model)
            store.transact('A', 'window1', lambda state: agent.run(state, '记待办：写周报'))
            _, other = store.transact('A', 'window2', lambda state: None)
            self.assertEqual(other['todos'], [])
            _, other_user = store.transact('B', 'window1', lambda state: None)
            self.assertEqual(other_user['todos'], [])
            _, resumed = SessionStore(directory).transact('A', 'window1', lambda state: None)
            self.assertEqual(len(resumed['todos']), 1)

    def test_failed_transaction_is_not_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SessionStore(directory)
            def fail(state):
                state['todos'].append({'text': 'bad'})
                raise ValueError('fail')
            with self.assertRaises(ValueError):
                store.transact('A', '1', fail)
            _, state = store.transact('A', '1', lambda state: None)
            self.assertEqual(state['todos'], [])


if __name__ == '__main__':
    unittest.main()
