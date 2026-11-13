#pragma once

#include <QObject>
#include <QNetworkAccessManager>
#include <QSet>
#include <QUrl>
#include <QVariant>

class QNetworkReply;

class ApiClient final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QString baseUrl READ baseUrl NOTIFY baseUrlChanged)
    Q_PROPERTY(bool authenticated READ authenticated NOTIFY authenticatedChanged)
public:
    explicit ApiClient(QObject *parent = nullptr);
    QString baseUrl() const { return m_baseUrl; }
    bool authenticated() const { return !m_token.isEmpty(); }
    Q_INVOKABLE bool configure(const QString &url);
    Q_INVOKABLE bool acceptToken(const QString &token);
    Q_INVOKABLE void logout();
    Q_INVOKABLE int request(const QString &method, const QString &path,
                            const QVariantMap &body, bool auth = true, bool plainText = false);
    Q_INVOKABLE void cancel(int requestId);
    Q_INVOKABLE void copyText(const QString &text);
signals:
    void baseUrlChanged();
    void authenticatedChanged();
    void configurationError(const QString &message);
    void succeeded(int requestId, const QVariant &data);
    void failed(int requestId, int status, const QString &message);
private:
    void clearSession();
    void reject(int id, int status, const QString &message);
    QNetworkAccessManager m_network;
    QSet<QNetworkReply *> m_replies;
    QString m_baseUrl;
    QByteArray m_token;
    int m_nextId = 0;
    int m_generation = 0;
};
