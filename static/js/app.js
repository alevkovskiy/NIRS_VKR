import { endpoints as api, session, request, collection } from './api.js';
const $ = (selector) => document.querySelector(selector);
const page = document.body.dataset.page;
const authPages = ['login', 'register'];
let leaving = false;
window.addEventListener('pagehide', () => { leaving = true; });
function el(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = String(text);
  return element;
}
function notice(message, success = false) {
  const target = $('#notice');
  target.replaceChildren(document.createTextNode(message));
  target.className = `notice${success ? ' success' : ''}`;
  target.hidden = false;
}
function report(error) {
  notice(error.message || 'Не удалось выполнить действие.');
  if (error.status === 401 && !authPages.includes(page)) {
    const link = el('a', '', ' Войти →'); link.href = '/auth/'; $('#notice').append(link);
    updateSessionUI();
  }
}
function clearNotice() { $('#notice').hidden = true; }
function updateSessionUI() {
  if ($('#logout')) $('#logout').hidden = !session.token();
  if ($('#signin')) $('#signin').hidden = Boolean(session.token());
}
function empty(target, title, description) {
  const box = el('div', 'empty');
  box.append(el('span', 'empty-symbol', '◇'), el('h2', '', title), el('p', '', description));
  target.replaceChildren(box);
}
function loading(target) { target.replaceChildren(el('p', 'loading', 'Загрузка…')); }
async function busy(button, action, label = 'Подождите…') {
  if (!button || button.disabled) return;
  const original = button.textContent;
  button.disabled = true; button.textContent = label;
  try { await action(); } catch (error) { report(error); }
  finally { button.disabled = false; button.textContent = original; }
}
async function load(target, action) {
  loading(target);
  try { await action(); }
  catch (error) { empty(target, 'Не удалось загрузить', 'Повторите попытку после проверки подключения и доступности сервера.'); report(error); }
}
const date = (value) => {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' });
};
const statuses = {
  in_progress: ['Выполняется', 'running'],
  submission_failed: ['Не отправлен', 'error'],
  submission_unknown: ['Требует проверки в GitHub', 'pending'],
  partially_succeeded: ['Частичный успех', 'pending'],
  succeeded: ['Успешно', 'success'], failed: ['Ошибка', 'error'],
  canceled: ['Отменён', ''], cancelled: ['Отменён', ''],
  inProgress: ['Выполняется', 'running'], running: ['Выполняется', 'running'],
  completed: ['Завершён', ''], notStarted: ['В очереди', 'pending'],
  pending: ['Ожидание', 'pending'], queued: ['В очереди', 'pending'],
  skipped: ['Пропущено', ''], partiallySucceeded: ['Частичный успех', 'pending'],
};
function badge(value) {
  const [label, style] = statuses[value] || [value || 'Нет данных', ''];
  return el('span', `badge ${style}`, label);
}
function idOf(data) {
  if (data?.id === undefined || data.id === null || String(data.id) === '') throw new Error('Сервер не вернул идентификатор объекта.');
  return encodeURIComponent(String(data.id));
}
function routeId() {
  const value = location.pathname.split('/').filter(Boolean).at(-1);
  if (!value) throw new Error('В адресе страницы отсутствует идентификатор.');
  return decodeURIComponent(value);
}
function details(target, values) {
  target.replaceChildren(...values.map(([label, value]) => {
    const group = el('div'); const dd = el('dd');
    dd.append(value instanceof Node ? value : document.createTextNode(String(value ?? '—')));
    group.append(el('dt', '', label), dd); return group;
  }));
}
function list(target, entries, kind) {
  if (!entries.length) {
    const labels = { chat: ['Диалогов пока нет', 'Создайте новый чат, чтобы задать первый вопрос.'], run: ['Запусков пока нет', 'Здесь появятся реальные результаты запусков пайплайнов.'], job: ['Джоб пока нет', 'Список появится, когда сервер получит информацию о выполнении.'] };
    empty(target, ...labels[kind]); return;
  }
  const paths = { chat: 'chats', run: 'runs', job: 'jobs' };
  target.replaceChildren(...entries.map((item) => {
    const link = el('a', 'item'); link.href = `/${paths[kind]}/${idOf(item)}`;
    const text = el('div');
    const title = kind === 'chat' ? item.title || `Диалог #${item.id}` : item.name || `${kind === 'run' ? 'Запуск' : 'Джоба'} #${item.id}`;
    const meta = kind === 'chat' ? date(item.last_activity_at || item.created_at) : `${item.pipeline_name || ''} ${date(item.created_at || item.started_at)}`.trim();
    text.append(el('div', 'item-title', title), el('div', 'item-meta', meta));
    link.append(text, kind === 'chat' ? el('span', 'muted', '↗') : badge(item.result || item.status));
    return link;
  }));
}
function title(value) { if (value) { $('#page-title').textContent = value; document.title = `${value} — TestOps Assistant`; } }
function query(values) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) if (value) params.set(key, value);
  return params.size ? `?${params}` : '';
}
async function readTextAttachment(file) {
  if (!file?.size) return null;
  if (!/\.(log|txt|md|csv|json|xml|ya?ml)$/i.test(file.name)) {
    throw new Error('Выберите лог или текстовый файл поддерживаемого формата.');
  }
  if (file.size > 10 * 1024 * 1024) throw new Error('Файл слишком большой. Максимум 10 МБ.');
  let text;
  try { text = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer()); }
  catch { throw new Error('Не удалось прочитать файл. Выберите текст в UTF-8.'); }
  if (!text.trim() || text.includes('\0')) throw new Error('Файл должен содержать непустой текст.');
  return { name: file.name, text };
}
function renderMessage(message) {
  const user = message.role === 'user'; const block = el('article', `message${user ? ' user' : ''}`);
  const body = el('div', 'message-body');
  if (message.attachment_name) body.append(el('div', 'message-attachment', message.attachment_name));
  const content = String(message.content ?? '');
  if (user) body.append(document.createTextNode(content));
  else {
    let start = 0;
    for (const match of content.matchAll(/(`{3,})[\s\S]*?\1|`[^`\n]+`|\*\*([^*\n]+)\*\*/g)) {
      body.append(document.createTextNode(content.slice(start, match.index)));
      body.append(match[2] ? el('strong', '', match[2]) : document.createTextNode(match[0]));
      start = match.index + match[0].length;
    }
    body.append(document.createTextNode(content.slice(start)));
  }
  block.append(el('div', 'message-label', user ? 'Вы' : 'Ассистент'), body);
  if (!user) {
    const download = el('button', 'button quiet', 'Скачать как текст');
    download.type = 'button';
    download.addEventListener('click', () => {
      const url = URL.createObjectURL(new Blob([content], { type: 'text/plain;charset=utf-8' }));
      const link = el('a');
      link.href = url; link.download = 'testops-response.txt';
      document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    });
    block.append(download);
  }
  return block;
}
async function auth() {
  if (page === 'login' && new URLSearchParams(location.search).has('registered')) notice('Аккаунт создан. Войдите с вашей почтой и паролем.', true);
  $('#auth-form').addEventListener('submit', (event) => {
    event.preventDefault(); clearNotice();
    const form = event.currentTarget;
    if (page === 'register' && form.elements.password.value !== form.elements.confirm_password.value) {
      notice('Пароли не совпадают.'); form.elements.confirm_password.focus(); return;
    }
    void busy(form.querySelector('button'), async () => {
      const result = await request(page === 'login' ? api.login : api.register, {
        method: 'POST', auth: false,
        body: { email: form.elements.email.value.trim(), password: form.elements.password.value },
      });
      if (page === 'register') { location.assign('/auth/?registered=1'); return; }
      if (typeof result?.access_token !== 'string' || !result.access_token.trim()) throw new Error('Сервер не вернул access_token.');
      session.save(result.access_token); location.assign('/');
    }, page === 'login' ? 'Входим…' : 'Создаём аккаунт…');
  });
}
async function dashboard() {
  await Promise.all([
    load($('#recent-chats'), async () => list($('#recent-chats'), collection(await request(api.chats)).slice(0, 4), 'chat')),
    load($('#recent-runs'), async () => list($('#recent-runs'), collection(await request(api.runs)).slice(0, 4), 'run')),
  ]);
}
async function chats() {
  const refresh = () => load($('#chat-list'), async () => {
    const result = await request(api.chats + query({ q: $('#query').value.trim() }));
    const items = collection(result);
    if (!items.length && $('#query').value.trim()) empty($('#chat-list'), 'Ничего не найдено', 'Попробуйте другой поисковый запрос.');
    else list($('#chat-list'), items, 'chat');
  });
  $('#chat-search').addEventListener('submit', (event) => { event.preventDefault(); clearNotice(); void refresh(); });
  $('#create-chat').addEventListener('click', (event) => void busy(event.currentTarget, async () => {
    clearNotice(); const result = await request(api.createChat, { method: 'POST', body: {} });
    location.assign(`/chats/${idOf(result)}`);
  }, 'Создаём…'));
  await refresh();
}
async function chat() {
  const id = routeId(); const messages = $('#messages'); const form = $('#message-form');
  const button = form.querySelector('button[type="submit"]'); const input = $('#message');
  const picker = $('#chat-file'); const attachButton = $('#attach-file');
  const removeButton = $('#remove-attachment'); const attachmentInfo = $('#attachment-info');
  const attachmentHint = attachmentInfo.textContent;
  const errorText = $('#message-error'); const count = $('#message-count');
  const maxMessage = 6000;
  const mode = $('#diagnosis-mode'); const diagnosisFields = $('#diagnosis-fields');
  const normalSendHint = $('#send-state').textContent;
  function updateMode() {
    diagnosisFields.hidden = !mode.checked;
    $('#message-fields').hidden = mode.checked;
    button.textContent = mode.checked ? 'Подготовить черновик' : 'Отправить ↑';
    $('#send-state').textContent = mode.checked ? '' : normalSendHint;
  }
  mode.checked = new URLSearchParams(location.search).has('diagnosis');
  mode.addEventListener('change', updateMode);
  updateMode();
  let attachment = null;
  let readingFile = false;
  function checkLength() {
    const length = Array.from(input.value.trim()).length;
    count.textContent = `${length.toLocaleString('ru-RU')} / 6 000`;
    const tooLong = length > maxMessage;
    input.setAttribute('aria-invalid', String(tooLong));
    errorText.hidden = !tooLong;
    errorText.textContent = tooLong ? 'Сообщение слишком большое. Максимум 6 000 символов.' : '';
    return !tooLong;
  }
  function clearAttachment() {
    attachment = null;
    picker.value = '';
    removeButton.hidden = true;
    attachmentInfo.textContent = attachmentHint;
  }
  input.addEventListener('input', checkLength);
  attachButton.addEventListener('click', () => picker.click());
  removeButton.addEventListener('click', clearAttachment);
  picker.addEventListener('change', async () => {
    const file = picker.files[0];
    if (!file) return;
    clearNotice();
    clearAttachment();
    readingFile = true;
    attachButton.disabled = true;
    try {
      attachment = await readTextAttachment(file);
      if (!attachment) throw new Error('Файл должен содержать непустой текст.');
      attachmentInfo.textContent = file.name;
      removeButton.hidden = false;
    } catch (error) { report(error); }
    finally { readingFile = false; attachButton.disabled = false; }
  });
  button.disabled = true; input.disabled = true;
  let ready = false;
  let messageCount = 0;
  let verifyBeforeSending = false;
  async function refreshHistory() {
    const result = await request(api.chat(id));
    if (!Array.isArray(result.messages)) throw new Error('В ответе сервера отсутствует список messages.');
    title(result.title || `Диалог #${id}`);
    messageCount = result.messages.length;
    if (messageCount) messages.replaceChildren(...result.messages.map(renderMessage));
    else empty(messages, 'С чего начнём?', 'Задайте вопрос ассистенту в поле ниже.');
    messages.scrollTop = messages.scrollHeight;
  }
  await load(messages, async () => {
    await refreshHistory();
    ready = true; button.disabled = false; input.disabled = false; attachButton.disabled = false;
  });
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!ready || button.disabled || readingFile) return;
    const diagnosis = mode.checked ? Object.fromEntries(
      [...diagnosisFields.querySelectorAll('[name]')].map((field) => [field.name, field.value.trim()])
    ) : null;
    const content = diagnosis ? '' : input.value.trim();
    if (diagnosis && !diagnosis.observed && !attachment) {
      notice('Опишите фактический результат или приложите журнал.');
      $('#observed').focus();
      return;
    }
    if (!diagnosis && !checkLength()) return;
    if (!diagnosis && !content && !attachment) { notice('Введите сообщение или прикрепите файл.'); return; }
    void busy(button, async () => {
      clearNotice(); input.disabled = true; attachButton.disabled = true; removeButton.disabled = true;
      mode.disabled = true; diagnosisFields.disabled = true;
      $('#send-state').textContent = 'Ассистент готовит ответ…';
      try {
        const previousCount = messageCount;
        if (verifyBeforeSending) await refreshHistory();
        verifyBeforeSending = false;
        if (messageCount === previousCount) {
          let result;
          try {
            result = await request(api.messages(id), { method: 'POST', body: { content, attachment, diagnosis } });
            if (typeof result?.assistant_message?.content !== 'string') {
              throw new Error('Сервер не вернул ответ. Перед повтором проверим историю.');
            }
          } catch (error) {
            verifyBeforeSending = !error.status || error.status === 409
              || (error.status >= 200 && error.status < 300);
            throw error;
          }
          messages.querySelector('.empty')?.remove();
          messages.append(renderMessage(result.user_message ?? { role: 'user', content }), renderMessage(result.assistant_message));
          messageCount += 2;
        }
        if (diagnosis) {
          for (const field of diagnosisFields.querySelectorAll('[name]')) field.value = '';
          mode.checked = false;
          history.replaceState(null, '', location.pathname);
        }
        if (!diagnosis) input.value = '';
        checkLength(); clearAttachment(); messages.scrollTop = messages.scrollHeight;
      } finally {
        input.disabled = false; attachButton.disabled = false; removeButton.disabled = false;
        mode.disabled = false; diagnosisFields.disabled = false;
        if (mode.checked) $('#observed').focus(); else input.focus();
      }
    }, 'Ожидание…').finally(updateMode);
  });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (!button.disabled) form.requestSubmit(); }
  });
}
const diagnosticStatus = { open: 'Открыт', resolved: 'Решён' };
const checkOutcome = { passed: 'Успешно', failed: 'Сбой', inconclusive: 'Недостаточно данных' };
const checkSource = { manual: 'Вручную', stand: 'Снимок стенда', ci: 'CI' };

function requestId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return [...bytes].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

function fillRunSelect(select, entries, selected, placeholder) {
  select.replaceChildren(new Option(placeholder, ''));
  for (const run of entries) {
    select.add(new Option(`#${run.id} · ${run.name}`, run.id));
  }
  if (selected) {
    if (!entries.some((run) => String(run.id) === selected)) {
      select.add(new Option(`#${selected}`, selected));
    }
    select.value = selected;
  }
}

async function diagnostics() {
  const parts = location.pathname.split('/').filter(Boolean);
  if (parts.length === 1) {
    $('#diagnostic-overview').hidden = false;
    const params = new URLSearchParams(location.search);
    const preselected = params.get('run_id');
    const runSelect = $('#diag-run');
    const initialRequestId = requestId();
    $('#diagnostic-create').open = params.has('new');
    fillRunSelect(runSelect, [], preselected, 'Без прогона');
    $('#diagnostic-form').addEventListener('submit', (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const fields = form.elements;
      const diagnosis = Object.fromEntries(
        ['bench', 'environment', 'steps', 'expected', 'observed']
          .map((key) => [key, fields[key].value.trim()])
      );
      const file = fields.attachment.files[0];
      const title = fields.title.value.trim();
      const run_id = fields.run_id.value ? Number(fields.run_id.value) : null;
      void busy(form.querySelector('button'), async () => {
        clearNotice();
        const attachment = await readTextAttachment(file);
        if (!diagnosis.observed && !attachment && !run_id) {
          throw new Error('Добавьте фактический результат, журнал или связанный прогон.');
        }
        const item = await request(api.diagnostics, {
          method: 'POST', body: { title, diagnosis, attachment, run_id, request_id: initialRequestId },
        });
        location.assign(`/diagnostics/${idOf(item)}`);
      }, 'Сохраняем…');
    });
    void request(api.runs).then((runs) => fillRunSelect(runSelect, collection(runs), runSelect.value || preselected, 'Без прогона')).catch(report);
    const target = $('#diagnostic-list');
    return load(target, async () => {
      const entries = collection(await request(api.diagnostics));
      if (!entries.length) return empty(target, 'Сессий пока нет', 'Опишите сбой, чтобы начать диагностику.');
      target.replaceChildren(...entries.map((item) => {
        const link = el('a', 'item'); link.href = `/diagnostics/${idOf(item)}`;
        const text = el('div');
        text.append(el('div', 'item-title', item.title), el('div', 'item-meta',
          [item.bench, date(item.created_at)].filter(Boolean).join(' · ')));
        link.append(text, badge(diagnosticStatus[item.status]));
        return link;
      }));
    });
  }

  $('#diagnostic-detail').hidden = false;
  const path = api.diagnostic(routeId());
  const statusButton = $('#diagnostic-status');
  const checkContainer = $('#diagnostic-checks');
  const ciForm = $('#ci-check-form');
  let session;
  let manualRequestId = requestId();
  const repeatRequestId = requestId();
  async function refresh() {
    session = await request(path);
    title(session.title);
    const runLink = el('a', '', session.run_id ? `#${session.run_id}` : '—');
    if (session.run_id) runLink.href = `/runs/${encodeURIComponent(session.run_id)}`;
    details($('#diagnostic-card'), [
      ['Статус', diagnosticStatus[session.status]], ['Стенд', session.bench || '—'],
      ['Окружение', session.environment || '—'], ['Шаги', session.steps || '—'],
      ['Ожидалось', session.expected || '—'], ['Наблюдалось', session.observed || '—'],
      ['Прогон CI', runLink],
    ]);
    $('#diagnostic-chat').href = `/chats/${encodeURIComponent(session.chat_id)}`;
    $('#diagnostic-log-panel').hidden = !session.log_excerpt;
    $('#diagnostic-log-name').textContent = session.log_name || 'Журнал';
    $('#diagnostic-log').textContent = session.log_excerpt || '';
    $('#import-stand').hidden = !session.stand_available;
    $('#repeat-ci').hidden = !session.run_id;
    statusButton.textContent = session.status === 'open' ? 'Отметить решённым' : 'Переоткрыть';
    if (!session.checks.length) return empty(checkContainer, 'Проверок пока нет', 'Запишите наблюдение или импортируйте результат.');
    checkContainer.replaceChildren(...session.checks.map((check) => {
      const row = el('div', 'item');
      const detail = el('div');
      detail.append(el('div', 'item-title', check.name), el('div', 'item-meta',
        [checkSource[check.source], date(check.recorded_at), check.note].filter(Boolean).join(' · ')));
      if (check.run_id) {
        const link = el('a', '', 'Открыть прогон');
        link.href = `/runs/${encodeURIComponent(check.run_id)}`;
        detail.append(link);
      }
      row.append(detail, badge(checkOutcome[check.outcome]));
      return row;
    }));
  }
  async function mutate(subpath, body) {
    clearNotice();
    await request(path + subpath, { method: 'POST', body });
    await refresh();
  }
  await refresh();
  statusButton.addEventListener('click', () => void busy(statusButton, () =>
    mutate('/status', { status: session.status === 'open' ? 'resolved' : 'open' })));
  const standButton = $('#import-stand');
  standButton.addEventListener('click', () => void busy(standButton, () => mutate('/stand', {})));
  const repeatButton = $('#repeat-ci');
  repeatButton.addEventListener('click', () => void busy(repeatButton, async () => {
    clearNotice();
    const run = await request(path + '/repeat', { method: 'POST', body: { request_id: repeatRequestId } });
    location.assign(`/runs/${idOf(run)}`);
  }, 'Запускаем…'));
  const reportButton = $('#diagnostic-report');
  reportButton.addEventListener('click', () => void busy(reportButton, async () => {
    clearNotice();
    await request(path + '/report', { method: 'POST', body: {} });
    location.assign(`/chats/${encodeURIComponent(session.chat_id)}`);
  }, 'Готовим черновик…'));
  $('#manual-check-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    void busy(form.querySelector('button'), async () => {
      await mutate('/checks', {
        name: values.get('check_name'), outcome: values.get('outcome'),
        note: values.get('note'), request_id: manualRequestId,
      });
      manualRequestId = requestId();
      form.reset();
    }, 'Сохраняем…');
  });
  ciForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const selected = ciForm.elements.run_id.value;
    if (selected) void busy(ciForm.querySelector('button'), () => mutate(`/ci/${encodeURIComponent(selected)}`, {}));
  });
  void request(api.runs).then((runs) =>
    fillRunSelect(ciForm.elements.run_id, collection(runs).filter((run) => run.status === 'completed'),
      null, 'Выберите прогон')).catch(report);
}

async function pipelines() {
  const refresh = () => load($('#pipeline-list'), async () => {
    const entries = collection(await request(api.pipelines));
    if (!entries.length) { empty($('#pipeline-list'), 'Пайплайнов пока нет', 'Настройте интеграцию с GitHub Actions на сервере.'); return; }
    $('#pipeline-list').replaceChildren(...entries.map((item) => {
      const card = el('a', 'pipeline-card'); card.href = `/pipelines/${idOf(item)}`;
      card.append(el('span', 'pipeline-icon', '↗'), el('h3', '', item.name || `Пайплайн #${item.id}`), el('p', 'muted', item.description || `ID ${item.id}`), el('span', 'muted', 'Открыть пайплайн →'));
      return card;
    }));
  });
  $('#refresh').addEventListener('click', (event) => void busy(event.currentTarget, refresh)); await refresh();
}
async function pipeline() {
  const id = routeId(); const info = $('#pipeline-info');
  await load(info, async () => {
    const result = await request(api.pipeline(id)); title(result.name || `Пайплайн #${id}`);
    details(info, [['ID', result.id], ['Название', result.name], ['Описание', result.description], ['Ветка по умолчанию', result.default_branch]]);
    $('#branch').value = result.default_branch || 'main';
    $('#start-pipeline').disabled = false;
  });
  $('#start-pipeline').addEventListener('click', (event) => void busy(event.currentTarget, async () => {
    clearNotice();
    const branch = $('#branch').value.trim();
    if (!branch) throw new Error('Укажите ветку для сборки.');
    const keyName = `nirs_start_${id}_${branch}`;
    const key = sessionStorage.getItem(keyName) || crypto.randomUUID();
    sessionStorage.setItem(keyName, key);
    const result = await request(api.startPipeline(id), {
      method: 'POST', body: { branch }, idempotencyKey: key,
    });
    sessionStorage.removeItem(keyName);
    location.assign(`/runs/${idOf(result)}`);
  }, 'Запускаем…'));
  await load($('#pipeline-runs'), async () => list($('#pipeline-runs'), collection(await request(api.runs + query({ pipeline_id: id }))), 'run'));
}
async function runs() {
  const params = new URLSearchParams(location.search);
  $('#pipeline-id').value = params.get('pipeline_id') || ''; $('#result').value = params.get('result') || '';
  const refresh = () => load($('#run-list'), async () => {
    const search = query({ pipeline_id: $('#pipeline-id').value.trim(), result: $('#result').value });
    history.replaceState(null, '', `/runs${search}`);
    list($('#run-list'), collection(await request(api.runs + search)), 'run');
  });
  $('#run-filters').addEventListener('submit', (event) => { event.preventDefault(); clearNotice(); void refresh(); }); await refresh();
}
async function run() {
  const id = routeId(); let timer; let stopped = false;
  function render(result) {
    if (!Array.isArray(result.jobs)) throw new Error('В ответе сервера отсутствует список jobs.');
    title(result.name || `Запуск #${id}`);
    details($('#run-info'), [['Запуск', result.id ?? id], ['Пайплайн', result.pipeline_name || result.pipeline_id], ['Статус', badge(result.result || result.status)], ['Начало', date(result.started_at || result.created_at)], ['Завершение', date(result.finished_at)], ['Ветка', result.branch], ['Коммит', result.commit_sha]]);
    list($('#job-list'), result.jobs, 'job');
    if (result.submission_error) notice(result.submission_error);
    renderArtifacts(result.artifacts || []);
    $('#diagnostic-from-run').href = `/diagnostics?new=1&run_id=${encodeURIComponent(id)}`;
    $('#diagnostic-from-run').hidden = false;
    $('#analyze-run').disabled = ['pending', 'queued', 'in_progress'].includes(result.status);
    const finished = ['submission_failed', 'submission_unknown', 'completed', 'canceled', 'cancelled', 'failed', 'succeeded', 'partiallySucceeded'].includes(result.status) || Boolean(result.finished_at);
    const again = !finished && !stopped;
    $('#poll-state').textContent = again ? 'Обновляем состояние каждые 5 секунд.' : 'Автоматическое обновление остановлено.';
    return again;
  }
  async function refresh(initial = false) {
    clearTimeout(timer);
    try {
      const result = await request(initial ? api.run(id) : api.status(id));
      if (render(result) && !leaving) timer = setTimeout(() => void refresh(), 5000);
    } catch (error) {
      stopped = true; $('#poll-state').textContent = 'Обновление приостановлено. Нажмите «Обновить», чтобы повторить.'; report(error);
    }
  }
  $('#analyze-run').addEventListener('click', (event) => void busy(event.currentTarget, async () => {
    clearNotice();
    const result = await request(api.analysis(id), { method: 'POST', body: {} });
    location.assign(`/chats/${idOf(result)}`);
  }, 'Анализируем…'));
  $('#refresh').addEventListener('click', (event) => void busy(event.currentTarget, async () => { stopped = false; clearNotice(); await refresh(true); }));
  window.addEventListener('pagehide', () => clearTimeout(timer), { once: true });
  await refresh(true);
}
function renderArtifacts(artifacts) {
  const target = $('#artifacts');
  if (!artifacts.length) {
    target.replaceChildren(el('p', 'muted', 'Пакеты и отчёты появятся после публикации артефактов в GitHub.'));
    return;
  }
  target.replaceChildren(...artifacts.map((artifact) => {
    const button = el('button', 'button', `Скачать ${artifact.name} (ZIP)`);
    button.type = 'button';
    button.addEventListener('click', () => void busy(button, async () => {
      const data = await request(api.artifact(artifact.id), { blob: true });
      const url = URL.createObjectURL(data);
      const link = el('a'); link.href = url; link.download = `artifact-${artifact.id}.zip`;
      document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    }, 'Скачиваем…'));
    return button;
  }));
}
async function connectionStatus() {
  if (!session.token()) return;
  const result = await request(api.system);
  document.querySelectorAll('.connection').forEach((item) => {
    item.replaceChildren(document.createTextNode(result.github.configured ? 'GitHub подключён' : 'GitHub не подключён'));
  });
  if ($('#integration-status')) {
    $('#integration-status').textContent = `${result.ollama.model}: ${result.ollama.available ? 'доступна' : 'недоступна'} · GitHub Actions: ${result.github.configured ? 'настроен' : 'ожидает настройки'}`;
  }
}
async function job() {
  const id = routeId();
  const refresh = () => load($('#job-info'), async () => {
    const result = await request(api.job(id)); title(result.name || `Джоба #${id}`);
    details($('#job-info'), [['ID', result.id], ['Название', result.name], ['Состояние', badge(result.result || result.status)], ['Начало', date(result.started_at)], ['Завершение', date(result.finished_at)]]);
    if (result.run_id !== undefined && result.run_id !== null) { $('#run-link').href = `/runs/${encodeURIComponent(String(result.run_id))}`; $('#run-link').hidden = false; }
  });
  $('#refresh').addEventListener('click', (event) => void busy(event.currentTarget, refresh));
  $('#load-log').addEventListener('click', (event) => void busy(event.currentTarget, async () => {
    clearNotice(); const log = await request(api.log(id), { text: true });
    $('#job-log').textContent = log || 'Журнал пока пуст.';
  }, 'Загружаем…'));
  await refresh();
}
async function init() {
  const section = { chat: 'chats', pipeline: 'pipelines', run: 'runs', job: 'runs' }[page] || page;
  document.querySelector(`[data-nav="${section}"]`)?.setAttribute('aria-current', 'page');
  updateSessionUI();
  $('#logout')?.addEventListener('click', (event) => void busy(event.currentTarget, async () => {
    await request(api.logout, { method: 'POST' });
    session.clear(); location.replace('/auth/');
  }));
  if (!authPages.includes(page)) void connectionStatus().catch(report);
  if (!authPages.includes(page) && page !== 'error' && !session.token()) {
    notice('Войдите в аккаунт, чтобы открыть ваши данные.');
    const link = el('a', '', ' Перейти ко входу →'); link.href = '/auth/'; $('#notice').append(link);
    if ($('#integration-status')) $('#integration-status').textContent = 'Войдите, чтобы проверить подключение модели и GitHub.';
    for (const selector of ['#recent-chats', '#recent-runs', '#chat-list', '#run-list', '#pipeline-list', '#messages']) {
      if ($(selector)) empty($(selector), 'Войдите в аккаунт', 'После входа здесь появятся ваши данные.');
    }
    document.querySelectorAll('main button').forEach((button) => { button.disabled = true; });
    return;
  }
  const handlers = { login: auth, register: auth, dashboard, chats, chat, diagnostics, pipelines, pipeline, runs, run, job };
  if (handlers[page]) await handlers[page]();
}
init().catch(report);
