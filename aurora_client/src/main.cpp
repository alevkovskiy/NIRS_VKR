#include <auroraapp.h>
#include <QGuiApplication>
#include <QQmlContext>
#include <QQuickView>
#include <QScopedPointer>
#include "apiclient.h"

int main(int argc, char *argv[])
{
    QScopedPointer<QGuiApplication> app(Aurora::Application::application(argc, argv));
    app->setOrganizationName(QStringLiteral("ru.nirs"));
    app->setApplicationName(QStringLiteral("Client"));
    app->setApplicationVersion(QStringLiteral("0.1.0"));
    ApiClient api;
    QScopedPointer<QQuickView> view(Aurora::Application::createView());
    view->rootContext()->setContextProperty(QStringLiteral("Api"), &api);
    view->setSource(Aurora::Application::pathTo(QStringLiteral("qml/Client.qml")));
    view->show();
    return app->exec();
}
