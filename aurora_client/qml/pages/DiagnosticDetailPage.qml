import QtQuick 2.0
import Sailfish.Silica 1.0
import "../components"
import "../js/Contract.js" as Contract

Page {
    id: page
    property string entityId
    property var session: null
    property string checkRequestId: Api.newRequestId()
    property string repeatRequestId: Api.newRequestId()
    property var outcomes: ["passed", "failed", "inconclusive"]
    readonly property bool busy: details.busy || mutation.busy || reportRequest.busy || repeatRequest.busy

    function openChat() {
        pageStack.push(Qt.resolvedUrl("ChatPage.qml"), {entityId: String(session.chat_id)})
    }

    Request {
        id: details
        responseType: "diagnostic"
        onSuccess: page.session = data
    }
    Request {
        id: mutation
        property bool manual: false
        onSuccess: {
            if (manual) {
                page.checkRequestId = Api.newRequestId()
                checkName.text = ""
                checkNote.text = ""
            }
            details.call("diagnostic", page.entityId)
        }
    }
    Request {
        id: reportRequest
        responseType: "message"
        onSuccess: page.openChat()
    }
    Request {
        id: repeatRequest
        onSuccess: {
            page.repeatRequestId = Api.newRequestId()
            pageStack.push(Qt.resolvedUrl("RunPage.qml"), {entityId: String(data.id)})
        }
    }
    Component.onCompleted: details.call("diagnostic", entityId)

    SilicaFlickable {
        anchors.fill: parent
        contentHeight: content.height + Theme.paddingLarge
        PullDownMenu {
            MenuItem { text: "Обновить"; enabled: !page.busy; onClicked: details.call("diagnostic", page.entityId) }
        }
        Column {
            id: content
            width: parent.width
            spacing: Theme.paddingMedium
            PageHeader { title: "Сессия" }
            Notice { text: details.error || mutation.error || reportRequest.error || repeatRequest.error }
            Notice { text: page.busy ? "Обрабатываем запрос…" : "" }
            Column {
                width: parent.width
                visible: page.session !== null
                enabled: !page.busy
                spacing: Theme.paddingMedium
                Notice { text: page.session ? page.session.title : "" }
                Info {
                    rows: page.session ? [
                        ["Статус", Contract.diagnosticStatus(page.session.status)],
                        ["Стенд", page.session.bench || "—"],
                        ["Окружение", page.session.environment || "—"],
                        ["Шаги", page.session.steps || "—"],
                        ["Ожидалось", page.session.expected || "—"],
                        ["Наблюдалось", page.session.observed || "—"]
                    ] : []
                }
                Entry {
                    width: parent.width
                    visible: !!page.session && !!page.session.run_id
                    title: "Связанный прогон"
                    onClicked: pageStack.push(Qt.resolvedUrl("RunPage.qml"), {entityId: String(page.session.run_id)})
                }
                Info {
                    visible: !!page.session && !!page.session.log_excerpt
                    rows: page.session && page.session.log_excerpt ? [[page.session.log_name, page.session.log_excerpt]] : []
                }
                Button {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Подготовить черновик"
                    onClicked: reportRequest.call("diagnosticReport", page.entityId, {})
                }
                Button {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "История анализа"
                    onClicked: page.openChat()
                }
                Button {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: page.session && page.session.status === "resolved" ? "Переоткрыть" : "Отметить решённым"
                    onClicked: {
                        mutation.manual = false
                        mutation.call("diagnosticStatus", page.entityId,
                                      {status: page.session.status === "resolved" ? "open" : "resolved"})
                    }
                }
                SectionHeader { text: "Проверки" }
                Button {
                    anchors.horizontalCenter: parent.horizontalCenter
                    visible: !!page.session && page.session.stand_available
                    text: "Импортировать снимок стенда"
                    onClicked: {
                        mutation.manual = false
                        mutation.call("diagnosticStand", page.entityId, {})
                    }
                }
                Button {
                    anchors.horizontalCenter: parent.horizontalCenter
                    visible: !!page.session && !!page.session.run_id
                    text: "Повторить связанный прогон"
                    onClicked: repeatRequest.call("diagnosticRepeat", page.entityId, {request_id: page.repeatRequestId})
                }
                Entry {
                    width: parent.width
                    title: "К пайплайнам CI"
                    onClicked: pageStack.push(Qt.resolvedUrl("CollectionPage.qml"), {kind: "pipelines"})
                }
                TextField {
                    id: ciRunId
                    width: parent.width
                    label: "ID завершённого прогона CI"
                    placeholderText: label
                    inputMethodHints: Qt.ImhDigitsOnly
                }
                Button {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Записать результат CI"
                    enabled: /^[1-9][0-9]*$/.test(ciRunId.text.trim())
                    onClicked: {
                        mutation.manual = false
                        mutation.call("diagnosticCi", {sessionId: page.entityId, runId: ciRunId.text.trim()}, {})
                    }
                }
                TextField {
                    id: checkName
                    width: parent.width
                    label: "Название проверки"
                    placeholderText: label
                    maximumLength: 120
                }
                ComboBox {
                    id: outcome
                    width: parent.width
                    label: "Результат"
                    menu: ContextMenu {
                        MenuItem { text: "Успешно" }
                        MenuItem { text: "Сбой" }
                        MenuItem { text: "Недостаточно данных" }
                    }
                }
                TextArea {
                    id: checkNote
                    width: parent.width
                    label: "Наблюдение"
                    placeholderText: label
                }
                Button {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Записать проверку"
                    enabled: checkName.text.trim().length > 0 && checkNote.length <= 1000 && outcome.currentIndex >= 0
                    onClicked: {
                        Qt.inputMethod.hide()
                        mutation.manual = true
                        mutation.call("diagnosticCheck", page.entityId, {
                            request_id: page.checkRequestId, name: checkName.text.trim(),
                            note: checkNote.text.trim(), outcome: page.outcomes[outcome.currentIndex]
                        })
                    }
                }
                Repeater {
                    model: page.session ? page.session.checks : []
                    Info {
                        rows: [[modelData.name, Contract.checkOutcome(modelData.outcome)],
                               [Contract.checkSource(modelData.source), modelData.note || Contract.date(modelData.recorded_at)]]
                    }
                }
            }
        }
        VerticalScrollDecorator {}
    }
}
