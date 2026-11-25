import QtQuick 2.0
import Sailfish.Silica 1.0
import "../components"
import "../js/Contract.js" as Contract

Page {
    id: page
    property string entityId
    property var run: ({})
    property bool loaded: false
    property bool polling: false
    readonly property bool foreground: status === PageStatus.Active && Qt.application.state === Qt.ApplicationActive
    function refresh(initial) {
        if (details.busy) return
        poll.stop()
        details.call(initial ? "run" : "status", entityId)
    }
    onForegroundChanged: {
        if (!foreground) { poll.stop(); details.cancel() }
        else if (Api.authenticated && (!loaded || polling)) refresh(true)
    }
    Request {
        id: details; responseType: "run"
        onSuccess: {
            page.run = data; page.loaded = true; page.polling = !Contract.finished(data)
            if (page.polling && page.foreground) poll.restart()
        }
        onFailure: { page.polling = false; poll.stop() }
    }
    Request {
        id: analysisRequest
        onSuccess: pageStack.push(Qt.resolvedUrl("ChatPage.qml"), {entityId: String(data.id)})
    }
    Timer { id: poll; interval: 5000; repeat: false; onTriggered: page.refresh(false) }
    SilicaFlickable {
        anchors.fill: parent
        contentHeight: content.height + Theme.paddingLarge
        PullDownMenu { MenuItem { text: "Обновить"; enabled: !details.busy; onClicked: page.refresh(true) } }
        Column {
            id: content; width: parent.width; spacing: Theme.paddingMedium
            PageHeader { title: "Запуск" }
            Notice { text: page.run.name || "Запуск #" + page.entityId }
            Notice { text: details.error }
            Notice { text: details.busy ? "Обновление…" : page.polling ? "Состояние обновляется каждые 5 секунд." : details.error ? "Автообновление остановлено. Повторите через меню «Обновить»." : page.loaded ? "Запуск завершён." : "" }
            Info {
                visible: page.loaded
                rows: [["ID", page.run.id], ["Пайплайн", page.run.pipeline_name || page.run.pipeline_id], ["Статус", Contract.status(page.run.result || page.run.status)], ["Создан", Contract.date(page.run.created_at)], ["Начало", Contract.date(page.run.started_at)], ["Завершение", Contract.date(page.run.finished_at)]]
            }
            Button {
                anchors.horizontalCenter: parent.horizontalCenter
                visible: page.loaded && Contract.finished(page.run)
                enabled: !analysisRequest.busy
                text: analysisRequest.busy ? "Разбираем прогон…" : "Разобрать прогон"
                onClicked: analysisRequest.call("analysis", page.entityId, {})
            }
            Notice { text: analysisRequest.error }
            SectionHeader { text: "Задачи" }
            Notice { text: page.loaded && !page.run.jobs.length ? "Задачи пока не появились." : "" }
            Repeater {
                model: page.run.jobs || []
                Entry { width: content.width; title: Contract.title(modelData, "jobs"); subtitle: Contract.status(modelData.result || modelData.status); onClicked: pageStack.push(Qt.resolvedUrl("JobPage.qml"), {entityId: String(modelData.id), parentRunId: page.entityId}) }
            }
        }
        VerticalScrollDecorator {}
    }
}
