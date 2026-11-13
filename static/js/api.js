// Change API addresses here if the server contract changes.
const segment = (value) => encodeURIComponent(String(value));
export const endpoints = {
  login: '/auth/send', register: '/auth/register/send', logout: '/auth/logout',
  system: '/api/system/status',
  analysis: (id) => `/api/runs/${segment(id)}/analysis`,
  artifact: (id) => `/api/artifacts/${segment(id)}/download`,
  chats: '/api/chats', createChat: '/chats/new',
  chat: (id) => `/api/chats/${segment(id)}`,
  messages: (id) => `/api/chats/${segment(id)}/messages`,
  pipelines: '/api/pipelines',
  pipeline: (id) => `/api/pipelines/${segment(id)}`,
  startPipeline: (id) => `/pipelines/${segment(id)}/start`,
  runs: '/api/runs', run: (id) => `/api/runs/${segment(id)}`,
  status: (id) => `/api/runs/${segment(id)}/status`,
  job: (id) => `/api/jobs/${segment(id)}`,
  log: (id) => `/jobs/${segment(id)}/log`,
};
const TOKEN_KEY = 'nirs_access_token';
export const session = {
  token: () => sessionStorage.getItem(TOKEN_KEY),
  save: (token) => sessionStorage.setItem(TOKEN_KEY, token),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
};
export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}
export async function request(url, { method = 'GET', body, auth = true, text = false, blob = false, idempotencyKey } = {}) {
  const headers = { Accept: text ? 'text/plain' : 'application/json' };
  if (auth) {
    const token = session.token();
    if (!token) throw new ApiError('Войдите в аккаунт, чтобы загрузить данные.', 401);
    headers.Authorization = `Bearer ${token}`;
  }
  if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  let response;
  try {
    response = await fetch(url, {
      method, headers, body: body === undefined ? undefined : JSON.stringify(body),
      credentials: 'omit', cache: 'no-store', redirect: 'error',
      signal: AbortSignal.timeout(120000),
    });
  } catch (error) {
    throw new ApiError(error.name === 'TimeoutError'
      ? 'Сервер не ответил вовремя. Проверьте результат перед повторной отправкой.'
      : 'Не удалось связаться с сервером. Проверьте подключение и повторите попытку.', 0);
  }
  if (!response.ok) {
    if (auth && response.status === 401) session.clear();
    let detail;
    try {
      const data = await response.json();
      if (typeof data.detail === 'string') detail = data.detail;
      else if (Array.isArray(data.detail)) detail = data.detail.map((entry) => entry.msg).join('; ');
    } catch { /* A proxy may return a non-JSON error page. */ }
    const fallback = {
      401: auth ? 'Сессия завершилась. Войдите в аккаунт повторно.' : 'Неверная почта или пароль.',
      403: 'Недостаточно прав для выполнения действия.',
      404: 'Данные не найдены или недоступны.',
      405: 'Это действие недоступно.',
      409: 'Действие конфликтует с текущим состоянием данных.',
      422: 'Проверьте заполненные поля.',
      429: 'Слишком много запросов. Попробуйте немного позже.',
    };
    throw new ApiError(response.status === 401 ? fallback[401] : detail || fallback[response.status] || 'Ошибка сервера. Повторите попытку позже.', response.status);
  }
  if (response.status === 204) return null;
  if (blob) return response.blob();
  if (text) return response.text();
  if (!response.headers.get('content-type')?.includes('application/json')) {
    throw new ApiError('Сервер вернул страницу вместо JSON. Проверьте адрес API.', response.status);
  }
  try { return await response.json(); }
  catch { throw new ApiError('Сервер вернул некорректный JSON.', response.status); }
}
export function collection(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  throw new ApiError('Ожидался список данных в формате JSON.', 200);
}
