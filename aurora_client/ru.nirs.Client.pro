TARGET = ru.nirs.Client
TEMPLATE = app
CONFIG += auroraapp c++11
QT += core gui qml quick network
SOURCES += src/main.cpp src/apiclient.cpp
HEADERS += src/apiclient.h

# auroraapp installs qml/, desktop and icons using the standard layout.
DISTFILES += ru.nirs.Client.desktop rpm/ru.nirs.Client.spec
OTHER_FILES += qml/Client.qml qml/pages/*.qml qml/components/*.qml qml/js/*.js
