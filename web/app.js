const $ = id => document.getElementById(id);
let sessions;
try { sessions = JSON.parse(localStorage.getItem('react-lab-sessions') || '[]'); if (!Array.isArray(sessions)) sessions = []; } catch { sessions = []; }
let current = sessionStorage.getItem('react-lab-active') || crypto.randomUUID();
let state = null;
let busy = false;
let loading = false;
let version = 0;
function element(tag, text, className) { const node = document.createElement(tag); node.textContent = text; if (className) node.className = className; return node; }
function persist() { localStorage.setItem('react-lab-sessions', JSON.stringify(sessions)); sessionStorage.setItem('react-lab-active', current); }
function error(message='') { $('error').textContent = message; $('error').hidden = !message; }
async function api(path, data) {
  const response = await fetch(path, data ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)} : {});
  const result = await response.json();
  if (!response.ok) throw Error(result.error || '请求失败');
  return result;
}
function controls() { $('send').disabled = busy || loading || !$('input').value.trim(); $('new').disabled = busy; $('status').textContent = busy ? '正在执行 ReAct 循环…' : loading ? '正在加载会话…' : '准备就绪'; }
function renderNav() {
  $('sessions').replaceChildren();
  for (const session of sessions) {
    const button = element('button', session.title, current === session.id ? 'active' : '');
    button.disabled = busy;
    button.append(element('small', session.id.slice(0,8)));
    button.onclick = () => select(session.id);
    $('sessions').append(button);
  }
  $('title').textContent = sessions.find(s=>s.id===current)?.title || '新的工作会话';
  $('session-id').textContent = 'SESSION / ' + current.slice(0,8);
}
function message(role, content) { const article=element('article','','message '+role); article.append(element('label',role==='user'?'你':'AGENT'),element('div',content,'bubble')); $('messages').append(article); }
function render() {
  renderNav();
  $('messages').replaceChildren();
  if (!state?.turns.length) {
    const welcome=element('div','','welcome'); welcome.append(element('div','↗','symbol'),element('h1','让想法开始执行。'),element('p','查找资料、完成计算，或记录下一件要做的事。每一步行动，都可以在右侧查看。'));
    const suggestions=element('div','','suggestions');
    for (const text of ['查杭州天气并记待办','计算 (128 + 72) * 3','搜索 ReAct Agent 的实现方法']) { const button=element('button',text+' ↗'); button.onclick=()=>{$('input').value=text; send();}; button.disabled=busy||loading; suggestions.append(button); }
    welcome.append(suggestions,element('small','天气与搜索为示例数据；自由对话请使用真实模型模式。')); $('messages').append(welcome);
  }
  for (const turn of state?.turns || []) { message('user',turn[0].content); const last=turn.at(-1); if(last.role==='assistant') message('assistant',last.content); }
  $('trace').replaceChildren();
  if (!state?.trace.length) $('trace').textContent='发送任务后，查看决策与工具结果。';
  for (const event of state?.trace || []) {
    const failed=event.ok===false||event.status.endsWith('error');
    const item=element('div','','trace-item'+(failed?' failed':''));
    item.append(element('b',event.tool || (event.type==='final'?'最终回复':'模型决策')),element('span',failed?'失败':event.status==='observation'?'已执行':'第 '+event.step+' 轮','tag'));
    item.append(element('p',event.thought || event.error || `${event.elapsed_ms} ms`));
    if(event.arguments || event.status==='observation') { const details=element('details'); details.append(element('summary','查看参数与结果'),element('pre',JSON.stringify(event,null,2))); item.append(details); }
    $('trace').append(item);
  }
  $('todos').replaceChildren(); $('count').textContent=state?.todos.length||0;
  if(!state?.todos.length) $('todos').textContent='暂无待办';
  for(const todo of state?.todos || []) $('todos').append(element('div',(todo.done?'✓ ':'○ ')+todo.text,'todo'));
  $('summary').textContent=state?.summary || '暂无压缩历史'; controls(); $('messages').scrollTop=$('messages').scrollHeight;
}
async function select(id) {
  if(busy) return;
  current=id; persist(); state=null; loading=true; const request=++version; error(); render();
  try { const result=await api('/api/session',{session:id}); if(request===version) state=result.state; }
  catch(e) { if(request===version) error(e.message); }
  finally { if(request===version) { loading=false; render(); } }
}
async function send() {
  const input=$('input').value.trim(); if(!input||busy||loading)return;
  busy=true; error(); controls(); renderNav(); $('input').value='';
  if(!state?.turns.length) $('messages').replaceChildren();
  message('user',input); const pending=element('div','正在查询模型并执行工具，请稍候…','pending'); $('messages').append(pending); $('messages').scrollTop=$('messages').scrollHeight;
  try {
    const result=await api('/api/chat',{session:current,input}); state=result.state;
    if(!sessions.some(s=>s.id===current)) sessions.unshift({id:current,title:input.slice(0,24)});
    persist();
  } catch(e) { error(e.message); $('input').value=input; }
  finally { busy=false; render(); $('input').focus(); }
}
$('new').onclick=()=>select(crypto.randomUUID());
$('composer').onsubmit=e=>{e.preventDefault();send();};
$('input').oninput=controls;
$('input').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();send();}};
async function init() {
  try { const config=await api('/api/config'); $('mode').textContent=config.mode; for(const tool of config.tools){const details=element('details'); details.append(element('summary',tool.name),element('p',tool.description),element('pre',JSON.stringify(tool.parameters,null,2))); $('tools').append(details);} await select(current); }
  catch(e){error('无法连接服务：'+e.message);$('mode').textContent='连接失败';}
}
render(); init();
