import QtQuick 2.0
import Sailfish.Silica 1.0
import "../components"

Page {
    id: page
    property string entityId
    property string heading: "Диалог"
    property var messages: []
    property bool ready: false
    function refresh() {
        if (sendRequest.busy || historyRequest.busy) return
        ready = false
        historyRequest.call("chat", entityId)
    }
    Request {
        id: historyRequest; responseType: "chat"
        onSuccess: { page.heading = data.title || "Диалог #" + page.entityId; page.messages = data.messages; page.ready = true }
    }
    Request {
        id: sendRequest; responseType: "message"
        property string sentContent: ""
        onSuccess: {
            page.messages = page.messages.concat([{role: "user", content: sentContent}, data.assistant_message])
            input.text = ""
            history.positionViewAtEnd()
        }
        onFailure: page.ready = false
    }
    Component.onCompleted: refresh()
    SilicaListView {
        id: history
        anchors { top: parent.top; left: parent.left; right: parent.right; bottom: composer.top }
        clip: true
        model: page.messages
        PullDownMenu { MenuItem { text: "Обновить историю"; enabled: !historyRequest.busy && !sendRequest.busy; onClicked: page.refresh() } }
        header: Column {
            width: history.width
            PageHeader { title: "Диалог" }
            Notice { text: page.heading }
            Notice { text: historyRequest.error }
            BusyIndicator { anchors.horizontalCenter: parent.horizontalCenter; running: historyRequest.busy; visible: running; size: BusyIndicatorSize.Medium }
            Notice { text: page.ready && !page.messages.length ? "Задайте первый вопрос ассистенту." : "" }
        }
        delegate: Column {
            width: history.width
            spacing: Theme.paddingSmall
            Label { x: Theme.horizontalPageMargin; text: modelData.role === "user" ? "Вы" : modelData.role === "assistant" ? "Ассистент" : String(modelData.role || "Сообщение"); color: Theme.highlightColor; font.pixelSize: Theme.fontSizeSmall }
            Label { x: Theme.horizontalPageMargin; width: parent.width - 2 * x; text: modelData.content; textFormat: Text.PlainText; wrapMode: Text.Wrap }
            Item { width: 1; height: Theme.paddingLarge }
        }
        VerticalScrollDecorator {}
    }
    Column {
        id: composer
        width: parent.width
        anchors.bottom: parent.bottom
        Notice { text: sendRequest.error }
        Notice { text: !page.ready && sendRequest.error ? "Текст сохранён. Обновите историю перед повторной отправкой: сервер мог уже принять сообщение." : "" }
        Notice { text: sendRequest.busy ? "Ассистент готовит ответ…" : "" }
        TextArea { id: input; width: parent.width; height: Math.min(implicitHeight, page.height * 0.28); placeholderText: "Сообщение"; label: "Ваш вопрос"; enabled: !sendRequest.busy }
        Button {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Отправить"
            enabled: page.ready && !sendRequest.busy && input.text.trim().length > 0
            onClicked: {
                sendRequest.sentContent = input.text.trim()
                input.focus = false
                sendRequest.call("messages", page.entityId, {content: sendRequest.sentContent})
            }
        }
        Item { width: 1; height: Theme.paddingSmall }
    }
}
