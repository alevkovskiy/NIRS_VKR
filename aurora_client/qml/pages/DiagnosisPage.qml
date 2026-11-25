import QtQuick 2.0
import Sailfish.Silica 1.0
import "../components"

Page {
    id: page
    property string chatId: ""
    property var draft
    property bool verifyBeforeSending: false
    readonly property bool withinLimits: steps.length <= 600 && expected.length <= 400
                                         && observed.length <= 1000 && logInput.length <= 8000
    readonly property bool busy: createRequest.busy || sendRequest.busy || historyRequest.busy

    function openReport() {
        pageStack.replace(Qt.resolvedUrl("ChatPage.qml"), {entityId: chatId})
    }

    function submit() {
        var logText = logInput.text
        draft = {
            diagnosis: {
                bench: bench.text.trim(),
                environment: environment.text.trim(),
                steps: steps.text.trim(),
                expected: expected.text.trim(),
                observed: observed.text.trim()
            }
        }
        if (logText.trim().length) draft.attachment = {name: "stand.log", text: logText}
        if (verifyBeforeSending) historyRequest.call("chat", chatId)
        else if (chatId.length) sendRequest.call("messages", chatId, draft)
        else createRequest.call("createChat", null, {title: "Диагностика у стенда"})
    }

    Request {
        id: createRequest
        onSuccess: {
            page.chatId = String(data.id)
            sendRequest.call("messages", page.chatId, page.draft)
        }
    }
    Request {
        id: sendRequest
        responseType: "message"
        onSuccess: page.openReport()
        onFailure: page.verifyBeforeSending = status === 0 || status === 409 || (status >= 200 && status < 300)
    }
    Request {
        id: historyRequest
        responseType: "chat"
        onSuccess: {
            page.verifyBeforeSending = false
            if (data.messages.length) page.openReport()
            else sendRequest.call("messages", page.chatId, page.draft)
        }
    }

    SilicaFlickable {
        anchors.fill: parent
        contentHeight: form.height + Theme.paddingLarge
        Column {
            id: form
            width: parent.width
            enabled: !page.busy
            PageHeader { title: "Карточка сбоя" }
            TextField {
                id: bench
                width: parent.width
                label: "Стенд"
                placeholderText: label
                maximumLength: 120
            }
            TextField {
                id: environment
                width: parent.width
                label: "Устройство и версия сборки"
                placeholderText: label
                maximumLength: 200
            }
            TextArea {
                id: steps
                width: parent.width
                label: "Шаги воспроизведения"
                placeholderText: label
            }
            TextArea {
                id: expected
                width: parent.width
                label: "Ожидаемый результат"
                placeholderText: label
            }
            TextArea {
                id: observed
                width: parent.width
                label: "Фактический результат"
                placeholderText: label
            }
            TextArea {
                id: logInput
                width: parent.width
                label: "Фрагмент журнала"
                placeholderText: "Вставьте фрагмент журнала"
            }
            Notice { text: "Опишите фактический результат или вставьте журнал." }
            Notice {
                text: page.withinLimits ? "" : "Сократите текст: шаги до 600, ожидание до 400, факт до 1 000, журнал до 8 000 символов."
            }
            Notice { text: historyRequest.error || sendRequest.error || createRequest.error }
            Notice { text: page.busy ? "Готовим черновик…" : "" }
            Button {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Подготовить черновик"
                enabled: !page.busy && page.withinLimits && (observed.text.trim().length > 0 || logInput.text.trim().length > 0)
                onClicked: {
                    Qt.inputMethod.hide()
                    page.submit()
                }
            }
        }
        VerticalScrollDecorator {}
    }
}
