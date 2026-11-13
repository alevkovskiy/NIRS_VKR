import QtQuick 2.0
import Sailfish.Silica 1.0
import "../components"
import "../js/Contract.js" as Contract

Page {
    id: page
    property string kind: "chats"
    property var entries: []
    property bool loaded: false
    property bool createUncertain: false
    property string searchText: ""
    property string pipelineFilter: ""
    property string resultFilter: ""
    readonly property string heading: ({chats: "Чаты", pipelines: "Пайплайны", runs: "Запуски"})[kind]
    function refresh() {
        var filters = kind === "chats" ? {q: searchText.trim()} : kind === "runs" ? {pipeline_id: pipelineFilter.trim(), result: resultFilter} : {}
        entries = []; loaded = false
        listRequest.call(kind, null, undefined, filters)
    }
    function open(item) {
        var name = kind === "chats" ? "ChatPage.qml" : kind === "pipelines" ? "PipelinePage.qml" : "RunPage.qml"
        pageStack.push(Qt.resolvedUrl(name), {entityId: String(item.id)})
    }
    Request { id: listRequest; responseType: "list"; onSuccess: { page.entries = data; page.loaded = true; page.createUncertain = false } }
    Request {
        id: createRequest; responseType: "id"
        onFailure: page.createUncertain = true
        onSuccess: pageStack.push(Qt.resolvedUrl("ChatPage.qml"), {entityId: String(data.id)})
    }
    Component.onCompleted: refresh()
    SilicaListView {
        id: list
        anchors.fill: parent
        model: page.entries
        PullDownMenu {
            MenuItem { text: "Обновить"; enabled: !listRequest.busy && !createRequest.busy; onClicked: page.refresh() }
            MenuItem { text: "Новый чат"; visible: page.kind === "chats"; enabled: !createRequest.busy && !page.createUncertain; onClicked: createRequest.call("createChat", null, {}) }
        }
        header: Column {
            width: list.width
            PageHeader { title: page.heading }
            SearchField { id: search; onTextChanged: page.searchText = text; width: parent.width; visible: page.kind === "chats"; placeholderText: "Поиск диалогов"; enabled: !listRequest.busy; EnterKey.onClicked: { focus = false; page.refresh() } }
            TextField { id: pipeline; onTextChanged: page.pipelineFilter = text; width: parent.width; visible: page.kind === "runs"; label: "ID пайплайна"; placeholderText: "Все пайплайны"; enabled: !listRequest.busy; EnterKey.onClicked: { focus = false; page.refresh() } }
            ComboBox {
                id: result; width: parent.width; visible: page.kind === "runs"; label: "Результат"; enabled: !listRequest.busy
                property var values: ["", "succeeded", "failed", "canceled", "partiallySucceeded"]
                onCurrentIndexChanged: page.resultFilter = values[currentIndex]
                menu: ContextMenu {
                    MenuItem { text: "Все" }
                    MenuItem { text: "Успешно" }
                    MenuItem { text: "Ошибка" }
                    MenuItem { text: "Отменён" }
                    MenuItem { text: "Частичный успех" }
                }
            }
            Button { anchors.horizontalCenter: parent.horizontalCenter; visible: page.kind !== "pipelines"; text: "Применить"; enabled: !listRequest.busy; onClicked: page.refresh() }
            Notice { text: listRequest.error }
            Notice { text: createRequest.error }
            Notice { text: page.createUncertain ? "Обновите список перед повторным созданием: сервер мог уже создать чат." : "" }
            Notice { text: createRequest.busy ? "Создаём чат…" : "" }
            BusyIndicator { anchors.horizontalCenter: parent.horizontalCenter; running: listRequest.busy; visible: running; size: BusyIndicatorSize.Medium }
            Notice { text: page.loaded && !page.entries.length ? (page.kind === "chats" ? "Диалоги не найдены. Создайте новый через меню сверху." : page.kind === "pipelines" ? "Пайплайнов пока нет. Интеграция настраивается на сервере." : "Запуски не найдены. Попробуйте изменить фильтры.") : "" }
        }
        delegate: Entry {
            width: list.width
            title: Contract.title(modelData, page.kind)
            subtitle: page.kind === "chats" ? Contract.date(modelData.last_activity_at || modelData.created_at) : page.kind === "pipelines" ? modelData.description || "ID " + modelData.id : Contract.status(modelData.result || modelData.status) + " · " + Contract.date(modelData.created_at)
            onClicked: page.open(modelData)
        }
        VerticalScrollDecorator {}
    }
}
