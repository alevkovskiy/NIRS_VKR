const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const c = vm.createContext({encodeURIComponent, Date, Qt: {formatDateTime: () => 'formatted'}});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../qml/js/Contract.js'), 'utf8'), c);
let passed = 0;
function test(name, fn) { fn(); ++passed; console.log('OK', name); }
const rejects = fn => assert.throws(fn);
test('all documented routes and encoded IDs', () => {
  const plain = {login:'/auth/send',register:'/auth/register/send',chats:'/api/chats',createChat:'/chats/new',pipelines:'/api/pipelines',runs:'/api/runs'};
  for (const [k,v] of Object.entries(plain)) assert.equal(c.route(k), v);
  const detail = {chat:'/api/chats/x%2Fy%3F%23',messages:'/api/chats/x%2Fy%3F%23/messages',pipeline:'/api/pipelines/x%2Fy%3F%23',startPipeline:'/pipelines/x%2Fy%3F%23/start',run:'/api/runs/x%2Fy%3F%23',status:'/api/runs/x%2Fy%3F%23/status',job:'/api/jobs/x%2Fy%3F%23',log:'/jobs/x%2Fy%3F%23/log'};
  for (const [k,v] of Object.entries(detail)) assert.equal(c.route(k,'x/y?#'),v);
  assert.equal(c.route('job',0),'/api/jobs/0');
  for (const invalid of [undefined,null,'',{},[]]) rejects(()=>c.route('chat',invalid));
  rejects(()=>c.route('unknown',12));
});
test('query escapes user input and preserves zero IDs', () => {
  assert.equal(c.query({q:'привет &?#',pipeline_id:0,result:''}), '?q=%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82%20%26%3F%23&pipeline_id=0');
  assert.equal(c.query({q:null,result:undefined}), '');
});
test('array and items envelope accepted, malformed lists rejected', () => {
  assert.equal(c.validate('list',[{id:0}]).length,1);
  assert.equal(c.validate('list',{items:[{id:'abc'}]}).length,1);
  for(const data of [null,{},'',{items:null},[null],[{}],[{id:''}]]) rejects(()=>c.validate('list',data));
});
test('authentication and registration response shapes', () => {
  c.validate('token',{access_token:'abc',token_type:'Bearer'});
  c.validate('any',null);
  for(const data of [null,{}, {access_token:''},{access_token:123},{access_token:'abc',token_type:'basic'}]) rejects(()=>c.validate('token',data));
});
test('chat history and send response validation protect draft', () => {
  c.validate('chat',{id:1,messages:[{role:'user',content:'<script>literal</script>'}]});
  c.validate('message',{assistant_message:{content:'response'}});
  for(const data of [{id:1},{id:1,messages:[{}]},{id:1,messages:null}]) rejects(()=>c.validate('chat',data));
  for(const data of [{},{assistant_message:null},{assistant_message:{content:10}}]) rejects(()=>c.validate('message',data));
});
test('run requires jobs and stops polling only on terminal state', () => {
  c.validate('run',{id:1,jobs:[{id:'build-1'}]});
  rejects(()=>c.validate('run',{id:1}));
  rejects(()=>c.validate('run',{id:1,jobs:[{}]}));
  for(const status of ['submission_failed','submission_unknown','completed','canceled','cancelled','failed','succeeded','partiallySucceeded']) assert.equal(c.finished({status}),true);
  for(const status of ['pending','in_progress','queued','running','inProgress','notStarted',undefined]) assert.equal(c.finished({status}),false);
  assert.equal(c.finished({status:'inProgress',finished_at:'2026-10-26T18:00:00Z'}),true);
  // A result can be available before all jobs finish; status remains authoritative.
  assert.equal(c.finished({status:'inProgress',result:'succeeded'}),false);
});
test('logs remain plain text, null rejected', () => {
  assert.equal(c.validate('text','<b>log</b>\n'),'<b>log</b>\n');
  assert.equal(c.validate('text',''),'');
  rejects(()=>c.validate('text',null));
});
test('credential validation and status/date labels', () => {
  assert.equal(c.credentials(' user@example.org ','secret','secret',true),'');
  assert.ok(c.credentials('invalid','secret','secret',true));
  assert.ok(c.credentials('user@example.org','','',false));
  assert.ok(c.credentials('user@example.org','abc','def',true));
  assert.equal(c.status('inProgress'),'Выполняется');
  assert.equal(c.status('in_progress'),'Выполняется');
  assert.equal(c.status('submission_failed'),'Не отправлен');
  assert.equal(c.status('newState'),'newState');
  assert.equal(c.date('invalid'),'—');
  assert.equal(c.date(null),'—');
});
console.log(`${passed} contract test groups passed`);
