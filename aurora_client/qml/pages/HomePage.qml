import QtQuick 2.0
import Sailfish.Silica 1.0
import "../components"
import "../js/Contract.js" as Contract

Page {
    id: page
    property var chats: []
    property var runs: []
    function refresh() { chatRequest.call("chats"); runRequest.call("runs") }
    Request { id: chatRequest; responseType: "list"; onSuccess: page.chats = data.slice(0, 4) }
    Request { id: runRequest; responseType: "list"; onSuccess: page.runs = data.slice(0, 4) }
    Component.onCompleted: refresh()
    SilicaFlickable {
        anchors.fill: parent
        contentHeight: content.height + Theme.paddingLarge
        PullDownMenu {
            MenuItem { text: "Выйти"; onClicked: Api.logout() }
            MenuItem { text: "Настройки сервера"; onClicked: pageStack.push(Qt.resolvedUrl("SettingsPage.qml")) }
            MenuItem { text: "Обновить"; enabled: !chatRequest.busy && !runRequest.busy; onClicked: page.refresh() }
        }
        Column {
            id: content
            width: parent.width
            PageHeader { title: "NIRS"; description: "Рабочее пространство" }
            Entry { width: parent.width; title: "Чаты"; subtitle: "Вопросы ассистенту и история диалогов"; onClicked: pageStack.push(Qt.resolvedUrl("CollectionPage.qml"), {kind: "chats"}) }
            Entry { width: parent.width; title: "Пайплайны"; subtitle: "Просмотр и запуск сборок"; onClicked: pageStack.push(Qt.resolvedUrl("CollectionPage.qml"), {kind: "pipelines"}) }
            Entry { width: parent.width; title: "Запуски"; subtitle: "Состояние, задачи и журналы"; onClicked: pageStack.push(Qt.resolvedUrl("CollectionPage.qml"), {kind: "runs"}) }
            SectionHeader { text: "Последние диалоги" }
            Notice { text: chatRequest.error }
            Notice { text: chatRequest.busy ? "Загрузка…" : !page.chats.length && !chatRequest.error ? "Диалогов пока нет. Создайте первый в разделе «Чаты»." : "" }
            Repeater {
                model: page.chats
                Entry { width: content.width; title: Contract.title(modelData, "chats"); subtitle: Contract.date(modelData.last_activity_at || modelData.created_at); onClicked: pageStack.push(Qt.resolvedUrl("ChatPage.qml"), {entityId: String(modelData.id)}) }
            }
            SectionHeader { text: "Последние запуски" }
            Notice { text: runRequest.error }
            Notice { text: runRequest.busy ? "Загрузка…" : !page.runs.length && !runRequest.error ? "Запусков пока нет." : "" }
            Repeater {
                model: page.runs
                Entry { width: content.width; title: Contract.title(modelData, "runs"); subtitle: Contract.status(modelData.result || modelData.status); onClicked: pageStack.push(Qt.resolvedUrl("RunPage.qml"), {entityId: String(modelData.id)}) }
            }
        }
        VerticalScrollDecorator {}
    }
}
