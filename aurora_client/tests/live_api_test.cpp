#include <QtTest>
#include <QElapsedTimer>
#include <QUuid>
#include "../src/apiclient.h"

// Opt-in integration check: uses a real local server and real Ollama.
// The caller must remove this disposable account after the test, even on failure.
class LiveApiTest : public QObject {
    Q_OBJECT
    QString error;

    bool call(ApiClient &api, const QString &method, const QString &path,
              const QVariantMap &body, QVariant &result, bool auth = true) {
        QSignalSpy ok(&api, &ApiClient::succeeded);
        QSignalSpy failed(&api, &ApiClient::failed);
        const auto id = api.request(method, path, body, auth);
        QElapsedTimer elapsed;
        elapsed.start();
        while (ok.isEmpty() && failed.isEmpty() && elapsed.elapsed() < 115000)
            QTest::qWait(25);
        if (!failed.isEmpty()) {
            error = QStringLiteral("HTTP %1: %2")
                .arg(failed.first().at(1).toInt())
                .arg(failed.first().at(2).toString());
            return false;
        }
        if (ok.isEmpty()) {
            api.cancel(id);
            error = QStringLiteral("Timed out waiting for API response");
            return false;
        }
        result = ok.first().at(1);
        return true;
    }

private slots:
    void liveChatLifecycle() {
        const QString url = QString::fromUtf8(qgetenv("NIRS_LIVE_API_URL"));
        const QString email = QString::fromUtf8(qgetenv("NIRS_LIVE_TEST_EMAIL"));
        if (url.isEmpty() || email.isEmpty())
            QSKIP("Set NIRS_LIVE_API_URL and a disposable NIRS_LIVE_TEST_EMAIL");
        QVERIFY(email.startsWith("aurora-live-") && email.endsWith("@example.org"));
        QCoreApplication::setOrganizationName("ru.nirs.tests");
        QCoreApplication::setApplicationName("LiveApi");
        ApiClient api;
        QVERIFY(api.configure(url));
        const QString password = QUuid::createUuid().toString();
        const QVariantMap credentials{{"email", email}, {"password", password}};
        QVariant data;
        QVERIFY2(call(api, "POST", "/auth/register/send", credentials, data, false),
                 qPrintable(error));
        QVERIFY2(call(api, "POST", "/auth/send", credentials, data, false),
                 qPrintable(error));
        QVERIFY(api.acceptToken(data.toMap().value("access_token").toString()));
        qInfo("Registered and authenticated through ApiClient");
        QVERIFY2(call(api, "GET", "/api/pipelines", {}, data), qPrintable(error));
        QVERIFY(!data.toList().isEmpty());
        QVERIFY2(call(api, "POST", "/chats/new", {}, data), qPrintable(error));
        const auto chatId = data.toMap().value("id").toString();
        QVERIFY(!chatId.isEmpty());
        const QString question = QString::fromUtf8(
            "Что означает код завершения 1 при сборке приложения? Ответь кратко.");
        QVERIFY2(call(api, "POST", "/api/chats/" + chatId + "/messages",
                      {{"content", question}}, data), qPrintable(error));
        const auto reply = data.toMap().value("assistant_message").toMap()
                              .value("content").toString();
        QVERIFY(!reply.trimmed().isEmpty());
        QVERIFY2(call(api, "GET", "/api/chats/" + chatId, {}, data), qPrintable(error));
        const auto messages = data.toMap().value("messages").toList();
        QCOMPARE(messages.size(), 2);
        QCOMPARE(messages.first().toMap().value("content").toString(), question);
        QCOMPARE(messages.last().toMap().value("role").toString(), QString("assistant"));
        QCOMPARE(messages.last().toMap().value("content").toString(), reply);
        qInfo().noquote() << "Saved model reply:" << reply;
        QVERIFY2(call(api, "POST", "/auth/logout", {}, data), qPrintable(error));
        QVERIFY(!call(api, "GET", "/api/pipelines", {}, data));
        QVERIFY(error.startsWith("HTTP 401:"));
        QVERIFY(!api.authenticated());
        qInfo("History persisted and the logged-out session was rejected");
    }
};
QTEST_GUILESS_MAIN(LiveApiTest)
#include "live_api_test.moc"
