import QtQuick 2.0
import Sailfish.Silica 1.0
import "../components"
import "../js/Contract.js" as Contract

Page {
    id: page
    property var sessions: []
    property bool loaded: false
    onStatusChanged: {
        if (status === PageStatus.Active) sessionsRequest.call("diagnostics")
    }

    Request {
        id: sessionsRequest
        responseType: "list"
        onSuccess: { page.sessions = data; page.loaded = true }
    }

    SilicaListView {
        id: list
        anchors.fill: parent
        model: page.sessions
        PullDownMenu {
            MenuItem { text: "Обновить"; onClicked: sessionsRequest.call("diagnostics") }
        }
        header: Column {
            width: list.width
            PageHeader { title: "Диагностика" }
            Button {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Описать сбой"
                onClicked: pageStack.push(Qt.resolvedUrl("DiagnosisPage.qml"))
            }
            Notice { text: sessionsRequest.error }
            Notice { text: sessionsRequest.busy ? "Загрузка…" : page.loaded && !page.sessions.length ? "Сессий пока нет." : "" }
        }
        delegate: Entry {
            width: list.width
            title: modelData.title
            subtitle: Contract.diagnosticStatus(modelData.status) + (modelData.bench ? " · " + modelData.bench : "")
            onClicked: pageStack.push(Qt.resolvedUrl("DiagnosticDetailPage.qml"), {entityId: String(modelData.id)})
        }
        VerticalScrollDecorator {}
    }
}
