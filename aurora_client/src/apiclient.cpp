#include "apiclient.h"

#include <QClipboard>
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QRegularExpression>
#include <QSettings>
#include <QTimer>

namespace {
QString fallback(int status)
{
    switch (status) {
    case 401: return QStringLiteral("Сессия завершилась или неверны почта и пароль. Войдите снова.");
    case 403: return QStringLiteral("Недостаточно прав для этого действия.");
    case 404: return QStringLiteral("Данные не найдены или метод API ещё не реализован на сервере.");
    case 405: return QStringLiteral("Сервер пока не поддерживает это действие.");
    case 409: return QStringLiteral("Действие конфликтует с текущим состоянием данных.");
    case 422: return QStringLiteral("Проверьте заполненные поля.");
    case 429: return QStringLiteral("Слишком много запросов. Попробуйте позже.");
    default: return QStringLiteral("Ошибка сервера (%1). Попробуйте позже.").arg(status);
    }
}
QString errorDetail(const QByteArray &bytes)
{
    const auto detail = QJsonDocument::fromJson(bytes).object().value("detail");
    if (detail.isString()) return detail.toString().left(2000);
    QStringList messages;
    for (const auto &entry : detail.toArray()) {
        const auto message = entry.toObject().value("msg").toString();
        if (!message.isEmpty()) messages.append(message);
    }
    return messages.join(QStringLiteral("; ")).left(2000);
}
}

ApiClient::ApiClient(QObject *parent) : QObject(parent)
{
    m_baseUrl = QSettings().value("server/url", "http://127.0.0.1:8000").toString();
}

bool ApiClient::configure(const QString &input)
{
    const QUrl url(input.trimmed(), QUrl::StrictMode);
    if (!url.isValid() || url.host().isEmpty()
        || (url.scheme() != "http" && url.scheme() != "https")
        || !url.userInfo().isEmpty() || url.hasQuery() || url.hasFragment()) {
        emit configurationError(QStringLiteral("Укажите полный HTTP(S)-адрес без пароля, параметров и фрагмента."));
        return false;
    }
    QString normalized = url.adjusted(QUrl::NormalizePathSegments).toString(QUrl::FullyEncoded);
    while (normalized.endsWith('/')) normalized.chop(1);
    if (normalized == m_baseUrl) return true;
    clearSession();
    m_baseUrl = normalized;
    QSettings().setValue("server/url", m_baseUrl);
    emit baseUrlChanged();
    return true;
}

bool ApiClient::acceptToken(const QString &token)
{
    // A Bearer credential is a single ASCII token, never an arbitrary header value.
    static const QRegularExpression bearer(QStringLiteral("\\A[A-Za-z0-9._~+/-]+=*\\z"));
    if (token.isEmpty() || token.size() > 16384 || !bearer.match(token).hasMatch()) return false;
    m_token = token.toLatin1();
    emit authenticatedChanged();
    return true;
}

void ApiClient::clearSession()
{
    ++m_generation;
    const auto replies = m_replies;
    for (auto *reply : replies) {
        reply->setProperty("cancelled", true);
        reply->abort();
    }
    const bool wasAuthenticated = authenticated();
    m_token.fill('\0');
    m_token.clear();
    if (wasAuthenticated) emit authenticatedChanged();
}
void ApiClient::logout() { clearSession(); }
void ApiClient::copyText(const QString &text) { QGuiApplication::clipboard()->setText(text); }

void ApiClient::reject(int id, int status, const QString &message)
{
    QTimer::singleShot(0, this, [=] { emit failed(id, status, message); });
}

int ApiClient::request(const QString &method, const QString &path,
                       const QVariantMap &body, bool auth, bool plainText)
{
    const int id = ++m_nextId;
    if ((method != "GET" && method != "POST") || !path.startsWith('/')
        || path.startsWith("//") || path.contains('#') || path.contains('\\')) {
        reject(id, 0, QStringLiteral("Некорректный адрес запроса."));
        return id;
    }
    if (auth && !authenticated()) {
        reject(id, 401, QStringLiteral("Войдите в аккаунт, чтобы загрузить данные."));
        return id;
    }
    const QUrl url = QUrl::fromEncoded((m_baseUrl + path).toUtf8(), QUrl::StrictMode);
    if (!url.isValid()) {
        reject(id, 0, QStringLiteral("Некорректный адрес сервера."));
        return id;
    }
    QNetworkRequest req(url);
    req.setRawHeader("Accept", plainText ? "text/plain" : "application/json");
    req.setRawHeader("Cache-Control", "no-store");
    req.setAttribute(QNetworkRequest::CacheLoadControlAttribute, QNetworkRequest::AlwaysNetwork);
    req.setAttribute(QNetworkRequest::CacheSaveControlAttribute, false);
    req.setAttribute(QNetworkRequest::CookieLoadControlAttribute, QNetworkRequest::Manual);
    req.setAttribute(QNetworkRequest::CookieSaveControlAttribute, QNetworkRequest::Manual);
#if QT_VERSION >= QT_VERSION_CHECK(5, 9, 0)
    req.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::ManualRedirectPolicy);
#else
    req.setAttribute(QNetworkRequest::FollowRedirectsAttribute, false);
#endif
    if (auth) req.setRawHeader("Authorization", "Bearer " + m_token);
    QNetworkReply *reply;
    if (method == "POST") {
        req.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
        reply = m_network.post(req, QJsonDocument::fromVariant(body).toJson(QJsonDocument::Compact));
    } else {
        reply = m_network.get(req);
    }
    reply->setProperty("requestId", id);
    m_replies.insert(reply);
    const int generation = m_generation;
    auto *timer = new QTimer(reply);
    timer->setSingleShot(true);
    connect(timer, &QTimer::timeout, reply, [reply] {
        reply->setProperty("timeout", true);
        reply->abort();
    });
    timer->start(120000);
    // Bound memory consumption, including logs. No partial success on truncation.
    connect(reply, &QNetworkReply::readyRead, reply, [reply] {
        if (reply->bytesAvailable() > 8 * 1024 * 1024) {
            reply->setProperty("tooLarge", true);
            reply->abort();
        }
    });
    connect(reply, &QNetworkReply::finished, this, [=] {
        timer->stop();
        m_replies.remove(reply);
        reply->deleteLater();
        if (generation != m_generation || reply->property("cancelled").toBool()) return;
        const int status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
        const QByteArray bytes = reply->readAll();
        if (reply->property("tooLarge").toBool() || bytes.size() > 8 * 1024 * 1024) {
            emit failed(id, 0, QStringLiteral("Ответ превышает 8 МиБ. Запросите меньший объём данных."));
            return;
        }
        if (reply->property("timeout").toBool()) {
            emit failed(id, 0, QStringLiteral("Сервер не ответил за 120 секунд. Проверьте результат перед повторной отправкой."));
            return;
        }
        if (status >= 300 && status < 400) {
            emit failed(id, status, QStringLiteral("Сервер перенаправляет запрос. Проверьте адрес API и завершающие слеши."));
            return;
        }
        if (status >= 400) {
            const QString detail = errorDetail(bytes);
            emit failed(id, status, status == 401 || detail.isEmpty() ? fallback(status) : detail);
            if (auth && status == 401) clearSession();
            return;
        }
        if (reply->error() != QNetworkReply::NoError || status == 0) {
            emit failed(id, 0, QStringLiteral("Нет связи с сервером. Проверьте сеть, адрес и сертификат. Перед повтором действия обновите данные."));
            return;
        }
        if (status == 204) { emit succeeded(id, QVariant()); return; }
        const auto contentType = reply->header(QNetworkRequest::ContentTypeHeader).toString().toLower();
        if (plainText) {
            if (!contentType.startsWith("text/plain")) {
                emit failed(id, status, QStringLiteral("Сервер вернул неверный формат журнала: ожидается text/plain."));
                return;
            }
            emit succeeded(id, QString::fromUtf8(bytes));
            return;
        }
        if (!contentType.startsWith("application/json") && !contentType.contains("+json")) {
            emit failed(id, status, QStringLiteral("Сервер вернул страницу вместо JSON. Метод API может быть ещё не реализован."));
            return;
        }
        QJsonParseError error;
        const auto document = QJsonDocument::fromJson(bytes, &error);
        if (error.error != QJsonParseError::NoError || document.isNull()) {
            emit failed(id, status, QStringLiteral("Сервер вернул некорректный JSON."));
            return;
        }
        emit succeeded(id, document.toVariant());
    });
    return id;
}

void ApiClient::cancel(int requestId)
{
    const auto replies = m_replies;
    for (auto *reply : replies) {
        if (reply->property("requestId").toInt() == requestId) {
            reply->setProperty("cancelled", true);
            reply->abort();
        }
    }
}
