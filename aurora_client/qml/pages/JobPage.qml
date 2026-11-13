import QtQuick 2.0
import Sailfish.Silica 1.0
import "../components"
import "../js/Contract.js" as Contract

Page {
    id: page
    property string entityId
    property string parentRunId: ""
    property var job: ({})
    property bool loaded: false
    property bool logLoaded: false
    property string logText: ""
    Request { id: details; onSuccess: { page.job = data; page.loaded = true } }
    Request { id: logRequest; responseType: "text"; onSuccess: { page.logText = data; page.logLoaded = true } }
    Component.onCompleted: details.call("job", entityId)
    SilicaFlickable {
        anchors.fill: parent
        contentHeight: content.height + Theme.paddingLarge
        PullDownMenu {
            MenuItem { text: "Обновить задачу"; enabled: !details.busy; onClicked: details.call("job", page.entityId) }
            MenuItem { text: "Копировать журнал"; enabled: page.logLoaded && page.logText.length > 0; onClicked: Api.copyText(page.logText) }
        }
        Column {
            id: content; width: parent.width; spacing: Theme.paddingMedium
            PageHeader { title: "Задача" }
            Notice { text: page.job.name || "Задача #" + page.entityId }
            Notice { text: details.error }
            Notice { text: details.busy ? "Загрузка…" : "" }
            Info { visible: page.loaded; rows: [["ID", page.job.id], ["Состояние", Contract.status(page.job.result || page.job.status)], ["Начало", Contract.date(page.job.started_at)], ["Завершение", Contract.date(page.job.finished_at)]] }
            Button {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "К запуску"
                visible: page.job.run_id !== undefined && page.job.run_id !== null || page.parentRunId.length > 0
                onClicked: {
                    var runId = page.job.run_id === undefined || page.job.run_id === null ? page.parentRunId : String(page.job.run_id)
                    var previous = pageStack.previousPage()
                    if (previous && previous.entityId === runId && previous.run !== undefined) pageStack.pop()
                    else pageStack.push(Qt.resolvedUrl("RunPage.qml"), {entityId: runId})
                }
            }
            Button { anchors.horizontalCenter: parent.horizontalCenter; text: logRequest.busy ? "Загрузка журнала…" : page.logLoaded ? "Обновить журнал" : "Загрузить журнал"; enabled: !logRequest.busy; onClicked: logRequest.call("log", page.entityId) }
            Notice { text: logRequest.error }
            Label {
                x: Theme.horizontalPageMargin; width: parent.width - 2 * x
                visible: page.logLoaded
                text: page.logText || "Журнал пока пуст."
                textFormat: Text.PlainText; wrapMode: Text.WrapAnywhere
                font.family: "monospace"; font.pixelSize: Theme.fontSizeExtraSmall
            }
        }
        VerticalScrollDecorator {}
    }
}
