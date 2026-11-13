import QtQuick 2.0
import Sailfish.Silica 1.0
import "../components"

Page {
    id: page
    property string error: ""
    Connections { target: Api; onConfigurationError: page.error = message }
    SilicaFlickable {
        anchors.fill: parent
        contentHeight: content.height
        Column {
            id: content
            width: parent.width
            spacing: Theme.paddingMedium
            PageHeader { title: "Сервер" }
            TextField { id: url; width: parent.width; text: Api.baseUrl; label: "Адрес API"; placeholderText: "https://nirs.example.ru"; inputMethodHints: Qt.ImhUrlCharactersOnly | Qt.ImhNoAutoUppercase }
            Notice { text: page.error }
            Notice { text: "Укажите корень сервера без /api. Допускается префикс пути, например https://host/nirs. На устройстве localhost означает само устройство — используйте адрес компьютера в сети." }
            Notice { text: "HTTPS защищает пароль и токен. HTTP предназначен для локальной разработки. При смене сервера потребуется войти заново." }
            Button {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Сохранить"
                onClicked: {
                    var wasAuthenticated = Api.authenticated
                    var oldUrl = Api.baseUrl
                    if (Api.configure(url.text) && (!wasAuthenticated || oldUrl === Api.baseUrl)) pageStack.pop()
                }
            }
        }
        VerticalScrollDecorator {}
    }
}
