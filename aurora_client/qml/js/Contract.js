// Shared with the web client's documented API. Keep URLs in this file.
function segment(id) {
    if ((typeof id !== 'string' && typeof id !== 'number') || String(id).length === 0)
        throw new Error('Сервер не вернул идентификатор объекта.');
    return encodeURIComponent(String(id));
}
function route(kind, id) {
    var routes = {
        login: '/auth/send', register: '/auth/register/send',
        chats: '/api/chats', createChat: '/chats/new',
        pipelines: '/api/pipelines', runs: '/api/runs'
    };
    if (routes[kind]) return routes[kind];
    var key = segment(id);
    switch (kind) {
    case 'chat': return '/api/chats/' + key;
    case 'messages': return '/api/chats/' + key + '/messages';
    case 'pipeline': return '/api/pipelines/' + key;
    case 'startPipeline': return '/pipelines/' + key + '/start';
    case 'run': return '/api/runs/' + key;
    case 'status': return '/api/runs/' + key + '/status';
    case 'job': return '/api/jobs/' + key;
    case 'log': return '/jobs/' + key + '/log';
    }
    throw new Error('Неизвестный метод API.');
}
function query(values) {
    var parts = [];
    for (var key in values) {
        if (values[key] !== '' && values[key] !== undefined && values[key] !== null)
            parts.push(encodeURIComponent(key) + '=' + encodeURIComponent(String(values[key])));
    }
    return parts.length ? '?' + parts.join('&') : '';
}
function object(data) { return data !== null && typeof data === 'object' && !Array.isArray(data); }
function requireObject(data) {
    if (!object(data)) throw new Error('Ожидался объект JSON.');
    return data;
}
function validate(type, data) {
    if (type === 'any') return data;
    if (type === 'text') {
        if (typeof data !== 'string') throw new Error('Ожидался текст журнала.');
        return data;
    }
    if (type === 'list') {
        var list = Array.isArray(data) ? data : object(data) ? data.items : null;
        if (!Array.isArray(list)) throw new Error('Ожидался список или объект с полем items.');
        for (var i = 0; i < list.length; ++i) { requireObject(list[i]); segment(list[i].id); }
        return list;
    }
    requireObject(data);
    if (type === 'token') {
        if (typeof data.access_token !== 'string' || !data.access_token.length
            || (data.token_type && String(data.token_type).toLowerCase() !== 'bearer'))
            throw new Error('Сервер не вернул Bearer access_token.');
    } else if (type === 'message') {
        if (!object(data.assistant_message) || typeof data.assistant_message.content !== 'string')
            throw new Error('Нет assistant_message.content. Обновите историю перед повторной отправкой.');
    } else {
        segment(data.id);
        if (type === 'chat') {
            if (!Array.isArray(data.messages)) throw new Error('В ответе отсутствует список messages.');
            for (var j = 0; j < data.messages.length; ++j)
                if (!object(data.messages[j]) || typeof data.messages[j].content !== 'string')
                    throw new Error('Некорректное сообщение в истории.');
        }
        if (type === 'run') {
            if (!Array.isArray(data.jobs)) throw new Error('В ответе отсутствует список jobs.');
            validate('list', data.jobs);
        }
    }
    return data;
}
function finished(run) {
    return Boolean(run.finished_at) || ['submission_failed', 'submission_unknown', 'completed', 'canceled', 'cancelled', 'failed', 'succeeded', 'partiallySucceeded'].indexOf(run.status) !== -1;
}
function status(value) {
    var titles = {
        in_progress: 'Выполняется', partially_succeeded: 'Частичный успех',
        submission_failed: 'Не отправлен', submission_unknown: 'Требует проверки в GitHub',
        succeeded: 'Успешно', failed: 'Ошибка', canceled: 'Отменён', cancelled: 'Отменён',
        inProgress: 'Выполняется', running: 'Выполняется', completed: 'Завершён',
        notStarted: 'В очереди', pending: 'Ожидание', queued: 'В очереди',
        skipped: 'Пропущено', partiallySucceeded: 'Частичный успех'
    };
    return titles[value] || value || 'Нет данных';
}
function date(value) {
    if (!value) return '—';
    var parsed = new Date(value);
    return isNaN(parsed.getTime()) ? '—' : Qt.formatDateTime(parsed, 'dd.MM.yyyy HH:mm');
}
function title(item, kind) {
    return item.title || item.name || ({chats: 'Диалог', pipelines: 'Пайплайн', runs: 'Запуск', jobs: 'Задача'}[kind] || 'Объект') + ' #' + item.id;
}
function credentials(email, password, confirm, register) {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) return 'Укажите корректную почту.';
    if (!password.length) return 'Введите пароль.';
    if (register && password !== confirm) return 'Пароли не совпадают.';
    return '';
}
