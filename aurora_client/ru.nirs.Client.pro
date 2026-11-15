TARGET = ru.nirs.Client
TEMPLATE = app
CONFIG += auroraapp c++11
QT += core gui qml quick network
SOURCES += src/main.cpp src/apiclient.cpp
HEADERS += src/apiclient.h

# auroraapp installs qml/ and the desktop entry; install icons explicitly.
ICON_SIZES = 86x86 108x108 128x128 172x172
for(size, ICON_SIZES) {
    eval(icon_$${size}.files = $$PWD/icons/$${size}/$${TARGET}.png)
    eval(icon_$${size}.path = /usr/share/icons/hicolor/$${size}/apps)
    INSTALLS += icon_$${size}
}
DISTFILES += ru.nirs.Client.desktop rpm/ru.nirs.Client.spec
OTHER_FILES += qml/Client.qml qml/pages/*.qml qml/components/*.qml qml/js/*.js
