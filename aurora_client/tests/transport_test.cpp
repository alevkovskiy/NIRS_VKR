#include <QtTest>
#include <QTcpServer>
#include <QTcpSocket>
#include <QJsonDocument>
#include <QSettings>
#include <QSharedPointer>
#include <QTemporaryDir>
#include "../src/apiclient.h"

// Local HTTP fixture: no production server, credentials or Azure account needed.
class Fixture : public QObject {
public:
    QTcpServer server;
    QByteArray body = "{\"id\":1}";
    QByteArray type = "application/json";
    int status = 200;
    bool hold = false;
    QList<QByteArray> requests;
    Fixture() {
        server.listen(QHostAddress::LocalHost, 0);
        connect(&server, &QTcpServer::newConnection, this, [this] {
            auto *socket = server.nextPendingConnection();
            auto buffer = QSharedPointer<QByteArray>::create();
            connect(socket, &QTcpSocket::disconnected, socket, &QObject::deleteLater);
            connect(socket, &QTcpSocket::readyRead, this, [this, socket, buffer] {
                buffer->append(socket->readAll());
                const int end = buffer->indexOf("\r\n\r\n");
                if (end < 0 || socket->property("handled").toBool()) return;
                int contentLength = 0;
                for (auto line : buffer->left(end).split('\n')) {
                    if (line.toLower().startsWith("content-length:")) contentLength = line.mid(15).trimmed().toInt();
                }
                if (buffer->size() < end + 4 + contentLength) return;
                socket->setProperty("handled", true);
                requests.append(*buffer);
                if (hold) return;
                QByteArray response = "HTTP/1.1 " + QByteArray::number(status) + " Test\r\nContent-Type: " + type
                    + "\r\nContent-Length: " + QByteArray::number(body.size()) + "\r\nConnection: close\r\n";
                if (status == 302) response += "Location: /redirect-target\r\n";
                socket->write(response + "\r\n" + body);
                socket->disconnectFromHost();
            });
        });
    }
    QString url() const { return QString("http://127.0.0.1:%1").arg(server.serverPort()); }
};

class TransportTest : public QObject {
    Q_OBJECT
    QTemporaryDir settings;
private slots:
    void initTestCase() {
        QVERIFY(settings.isValid());
        QCoreApplication::setOrganizationName("nirs-tests");
        QCoreApplication::setApplicationName("transport");
        QSettings::setDefaultFormat(QSettings::IniFormat);
        QSettings::setPath(QSettings::IniFormat, QSettings::UserScope, settings.path());
    }
    void sendsJsonAndBearer() {
        Fixture fixture;
        ApiClient api;
        QVERIFY(api.configure(fixture.url()));
        QVERIFY(api.acceptToken("test.token-123"));
        QSignalSpy ok(&api, &ApiClient::succeeded);
        api.request("POST", "/api/chats/a%2Fb/messages", {{"content", "hello"}});
        QTRY_COMPARE(ok.count(), 1);
        QCOMPARE(fixture.requests.size(), 1);
        const auto request = fixture.requests.first();
        QVERIFY(request.startsWith("POST /api/chats/a%2Fb/messages HTTP/1.1"));
        QVERIFY(request.contains("Authorization: Bearer test.token-123"));
        QVERIFY(request.contains("Content-Type: application/json"));
        QVERIFY(request.endsWith("{\"content\":\"hello\"}"));
        QCOMPARE(ok.first().at(1).toMap().value("id").toInt(), 1);
    }
    void loginHasNoBearer() {
        Fixture fixture;
        ApiClient api; api.configure(fixture.url()); api.acceptToken("test-token");
        QSignalSpy ok(&api, &ApiClient::succeeded);
        api.request("POST", "/auth/send", {{"email", "test@example.org"}, {"password", "test"}}, false);
        QTRY_COMPARE(ok.count(), 1);
        QVERIFY(!fixture.requests.first().contains("Authorization:"));
    }
    void rejectsUnauthenticatedLocally() {
        Fixture fixture;
        ApiClient api; api.configure(fixture.url());
        QSignalSpy error(&api, &ApiClient::failed);
        const auto id = api.request("GET", "/api/chats", {});
        QTRY_COMPARE(error.count(), 1);
        QCOMPARE(error.first().at(0).toInt(), id);
        QCOMPARE(error.first().at(1).toInt(), 401);
        QCOMPARE(fixture.requests.size(), 0);
    }
    void unauthorizedClearsSession() {
        Fixture fixture; fixture.status = 401; fixture.body = "{\"detail\":\"secret server detail\"}";
        ApiClient api; api.configure(fixture.url()); api.acceptToken("test-token");
        QSignalSpy error(&api, &ApiClient::failed);
        api.request("GET", "/api/chats", {});
        QTRY_COMPARE(error.count(), 1);
        QVERIFY(!api.authenticated());
        QVERIFY(!error.first().at(2).toString().contains("secret"));
    }
    void redirectsNeverFollowed() {
        Fixture fixture; fixture.status = 302;
        ApiClient api; api.configure(fixture.url()); api.acceptToken("test-token");
        QSignalSpy error(&api, &ApiClient::failed);
        api.request("GET", "/api/chats", {});
        QTRY_COMPARE(error.count(), 1);
        QCOMPARE(error.first().at(1).toInt(), 302);
        QCOMPARE(fixture.requests.size(), 1);
    }
    void rejectsHtmlAndMalformedJson_data() {
        QTest::addColumn<QByteArray>("type"); QTest::addColumn<QByteArray>("body");
        QTest::newRow("html") << QByteArray("text/html") << QByteArray("<html>Login</html>");
        QTest::newRow("broken-json") << QByteArray("application/json") << QByteArray("{bad");
    }
    void rejectsHtmlAndMalformedJson() {
        QFETCH(QByteArray, type); QFETCH(QByteArray, body);
        Fixture fixture; fixture.type = type; fixture.body = body;
        ApiClient api; api.configure(fixture.url());
        QSignalSpy error(&api, &ApiClient::failed);
        api.request("GET", "/test", {}, false);
        QTRY_COMPARE(error.count(), 1);
    }
    void accepts204AndPlainText() {
        Fixture fixture; fixture.status = 204; fixture.body.clear();
        ApiClient api; api.configure(fixture.url());
        QSignalSpy ok(&api, &ApiClient::succeeded);
        api.request("POST", "/auth/register/send", {}, false);
        QTRY_COMPARE(ok.count(), 1);
        QVERIFY(!ok.first().at(1).isValid());
        fixture.status = 200; fixture.type = "text/plain; charset=utf-8"; fixture.body = "<script>plain</script>\n";
        api.request("GET", "/jobs/1/log", {}, false, true);
        QTRY_COMPARE(ok.count(), 2);
        QCOMPARE(ok.at(1).at(1).toString(), QString::fromUtf8(fixture.body));
    }
    void validationDetails() {
        Fixture fixture; fixture.status = 422; fixture.body = "{\"detail\":[{\"msg\":\"bad email\"},{\"msg\":\"bad password\"}]}";
        ApiClient api; api.configure(fixture.url());
        QSignalSpy error(&api, &ApiClient::failed);
        api.request("POST", "/auth/send", {}, false);
        QTRY_COMPARE(error.count(), 1);
        QCOMPARE(error.first().at(2).toString(), QString("bad email; bad password"));
    }
    void cancelsAndDiscardsLateReplies() {
        Fixture fixture; fixture.hold = true;
        ApiClient api; api.configure(fixture.url()); api.acceptToken("test-token");
        QSignalSpy error(&api, &ApiClient::failed); QSignalSpy ok(&api, &ApiClient::succeeded);
        const int id = api.request("GET", "/api/chats", {});
        QTRY_COMPARE(fixture.requests.size(), 1);
        api.cancel(id);
        QCoreApplication::processEvents();
        QCOMPARE(error.count(), 0); QCOMPARE(ok.count(), 0);
        api.request("GET", "/api/runs", {});
        QTRY_COMPARE(fixture.requests.size(), 2);
        api.logout();
        QCoreApplication::processEvents();
        QCOMPARE(error.count(), 0); QCOMPARE(ok.count(), 0);
        QVERIFY(!api.authenticated());
    }
    void configurationAndHeaderValidation() {
        ApiClient api;
        QVERIFY(!api.configure("file:///etc/passwd"));
        QVERIFY(!api.configure("https://user:password@host"));
        QVERIFY(!api.configure("https://host/?secret=1"));
        QVERIFY(!api.configure("https://host/#fragment"));
        QVERIFY(!api.acceptToken("token\r\nInjected: value"));
        QVERIFY(!api.acceptToken(" "));
        QVERIFY(!api.acceptToken("abc\n"));
        QVERIFY(api.configure("https://example.org/nirs/"));
        QCOMPARE(api.baseUrl(), QString("https://example.org/nirs"));
        QVERIFY(api.acceptToken("abc"));
        QVERIFY(api.configure("https://other.example.org"));
        QVERIFY(!api.authenticated());
        QCOMPARE(QSettings().value("server/url").toString(), api.baseUrl());
        QVERIFY(!QSettings().contains("token"));
    }
};
QTEST_GUILESS_MAIN(TransportTest)
#include "transport_test.moc"
