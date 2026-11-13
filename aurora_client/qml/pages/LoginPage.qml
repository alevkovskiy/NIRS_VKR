import QtQuick 2.0
import Sailfish.Silica 1.0
import "../components"
import "../js/Contract.js" as Contract

Page {
    id: page
    property bool registration: false
    property string localNotice: ""
    Request {
        id: action
        responseType: page.registration ? "any" : "token"
        onSuccess: {
            if (page.registration) {
                page.registration = false
                password.text = ""; confirm.text = ""
                page.localNotice = "Аккаунт создан. Войдите с вашей почтой и паролем."
            } else {
                var token = data.access_token
                password.text = ""; confirm.text = ""
                if (!Api.acceptToken(token)) page.localNotice = "Сервер вернул некорректный Bearer-токен."
            }
        }
    }
    function submit() {
        localNotice = Contract.credentials(email.text, password.text, confirm.text, registration)
        if (localNotice) return
        email.focus = false; password.focus = false; confirm.focus = false
        action.call(registration ? "register" : "login", null, {email: email.text.trim(), password: password.text})
    }
    SilicaFlickable {
        anchors.fill: parent
        contentHeight: content.height + Theme.paddingLarge
        PullDownMenu { MenuItem { text: "Настройки сервера"; enabled: !action.busy; onClicked: pageStack.push(Qt.resolvedUrl("SettingsPage.qml")) } }
        Column {
            id: content
            width: parent.width
            spacing: Theme.paddingMedium
            PageHeader { title: page.registration ? "Создать аккаунт" : "Вход в NIRS"; description: "Чаты · Пайплайны · Запуски" }
            Notice { text: page.localNotice }
            Notice { text: action.error }
            TextField {
                id: email; width: parent.width; label: "Электронная почта"; placeholderText: "name@example.com"
                inputMethodHints: Qt.ImhEmailCharactersOnly | Qt.ImhNoAutoUppercase
                enabled: !action.busy
                EnterKey.onClicked: password.focus = true
            }
            PasswordField { id: password; width: parent.width; label: "Пароль"; placeholderText: "Пароль"; enabled: !action.busy; EnterKey.onClicked: { if (page.registration) confirm.focus = true; else page.submit() } }
            PasswordField { id: confirm; width: parent.width; label: "Повтор пароля"; placeholderText: "Повторите пароль"; visible: page.registration; enabled: !action.busy; EnterKey.onClicked: page.submit() }
            Button { anchors.horizontalCenter: parent.horizontalCenter; text: action.busy ? "Подождите…" : page.registration ? "Зарегистрироваться" : "Войти"; enabled: !action.busy; onClicked: page.submit() }
            Button {
                anchors.horizontalCenter: parent.horizontalCenter
                text: page.registration ? "Уже есть аккаунт" : "Создать аккаунт"
                enabled: !action.busy
                onClicked: { page.registration = !page.registration; page.localNotice = ""; action.error = ""; confirm.text = ""; password.text = "" }
            }
            Notice { text: "Сервер: " + Api.baseUrl }
        }
        VerticalScrollDecorator {}
    }
}
