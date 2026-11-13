import QtQuick 2.0
import Sailfish.Silica 1.0
import "../components"
import "../js/Contract.js" as Contract

Page {
    id: page
    property string entityId
    property var pipeline: ({})
    property var runs: []
    property bool loaded: false
    property bool uncertain: false
    function refresh() {
        if (details.busy || history.busy || start.busy) return
        details.call("pipeline", entityId)
        history.call("runs", null, undefined, {pipeline_id: entityId})
    }
    Request { id: details; onSuccess: { page.pipeline = data; page.loaded = true } }
    Request { id: history; responseType: "list"; onSuccess: { page.runs = data; page.uncertain = false } }
    Request {
        id: start; responseType: "id"
        onSuccess: pageStack.push(Qt.resolvedUrl("RunPage.qml"), {entityId: String(data.id)})
        onFailure: page.uncertain = true
    }
    Component.onCompleted: refresh()
    SilicaFlickable {
        anchors.fill: parent
        contentHeight: content.height + Theme.paddingLarge
        PullDownMenu { MenuItem { text: "Обновить"; enabled: !details.busy && !history.busy && !start.busy; onClicked: page.refresh() } }
        Column {
            id: content; width: parent.width; spacing: Theme.paddingMedium
            PageHeader { title: "Пайплайн" }
            Notice { text: details.error }
            Notice { text: details.busy ? "Загрузка…" : "" }
            Info { visible: page.loaded; rows: [["ID", page.pipeline.id], ["Название", page.pipeline.name], ["Описание", page.pipeline.description]] }
            Button { anchors.horizontalCenter: parent.horizontalCenter; text: start.busy ? "Запускаем…" : "Запустить пайплайн"; enabled: page.loaded && !start.busy && !page.uncertain; onClicked: start.call("startPipeline", page.entityId, {}) }
            Notice { text: start.error }
            Notice { text: page.uncertain ? "Проверьте список запусков через «Обновить» перед повторной отправкой: сервер мог уже выполнить запуск." : "" }
            SectionHeader { text: "Запуски пайплайна" }
            Notice { text: history.error }
            Notice { text: history.busy ? "Загрузка запусков…" : !page.runs.length && !history.error ? "Запусков пока нет." : "" }
            Repeater {
                model: page.runs
                Entry { width: content.width; title: Contract.title(modelData, "runs"); subtitle: Contract.status(modelData.result || modelData.status) + " · " + Contract.date(modelData.created_at); onClicked: pageStack.push(Qt.resolvedUrl("RunPage.qml"), {entityId: String(modelData.id)}) }
            }
        }
        VerticalScrollDecorator {}
    }
}
