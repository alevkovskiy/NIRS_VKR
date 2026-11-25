import QtQuick 2.0
import Sailfish.Silica 1.0
import "../components"

Page {
    id: page
    property string sourceRunId: ""
    property string requestId: Api.newRequestId()
    readonly property bool withinLimits: steps.length <= 600 && expected.length <= 400
                                         && observed.length <= 1000 && logInput.length <= 8000

    function submit() {
        var draft = {
            request_id: page.requestId,
            title: summary.text.trim(),
            diagnosis: {
                bench: bench.text.trim(),
                environment: environment.text.trim(),
                steps: steps.text.trim(),
                expected: expected.text.trim(),
                observed: observed.text.trim()
            }
        }
        if (sourceRunId.length) draft.run_id = Number(sourceRunId)
        if (logInput.text.trim().length) draft.attachment = {name: "stand.log", text: logInput.text}
        createRequest.call("createDiagnostic", null, draft)
    }

    Request {
        id: createRequest
        onSuccess: pageStack.replace(Qt.resolvedUrl("DiagnosticDetailPage.qml"), {entityId: String(data.id)})
    }

    SilicaFlickable {
        anchors.fill: parent
        contentHeight: form.height + Theme.paddingLarge
        Column {
            id: form
            width: parent.width
            enabled: !createRequest.busy
            PageHeader { title: "Карточка сбоя" }
            TextField {
                id: summary
                width: parent.width
                label: "Краткое название сбоя"
                placeholderText: label
                maximumLength: 120
            }
            Notice { text: page.sourceRunId ? "Связанный прогон CI #" + page.sourceRunId : "" }
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
            Notice { text: page.sourceRunId ? "" : "Опишите фактический результат или вставьте журнал." }
            Notice {
                text: page.withinLimits ? "" : "Сократите текст: шаги до 600, ожидание до 400, факт до 1 000, журнал до 8 000 символов."
            }
            Notice { text: createRequest.error }
            Notice { text: createRequest.busy ? "Сохраняем сессию…" : "" }
            Button {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Сохранить сессию"
                enabled: !createRequest.busy && page.withinLimits && summary.text.trim().length > 0
                         && (observed.text.trim().length > 0 || logInput.text.trim().length > 0 || page.sourceRunId.length > 0)
                onClicked: {
                    Qt.inputMethod.hide()
                    page.submit()
                }
            }
        }
        VerticalScrollDecorator {}
    }
}
