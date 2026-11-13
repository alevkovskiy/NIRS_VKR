import QtQuick 2.0
import "../js/Contract.js" as Contract

Item {
    id: root
    visible: false
    property int activeId: -1
    property bool busy: false
    property string error: ""
    property string responseType: "object"
    signal success(var data)
    signal failure(int status)
    function call(kind, id, body, filters) {
        if (busy) return
        error = ""
        try {
            var path = Contract.route(kind, id) + Contract.query(filters || {})
            var method = body === undefined ? "GET" : "POST"
            busy = true
            activeId = Api.request(method, path, body || {}, kind !== "login" && kind !== "register", kind === "log")
        } catch (e) { busy = false; error = e.message; failure(0) }
    }
    function cancel() {
        if (busy) Api.cancel(activeId)
        activeId = -1
        busy = false
    }
    Connections {
        target: Api
        onSucceeded: {
            if (requestId !== root.activeId) return
            root.busy = false
            root.activeId = -1
            try { var validated = Contract.validate(root.responseType, data) }
            catch (e) { root.error = e.message; root.failure(0); return }
            root.success(validated)
        }
        onFailed: {
            if (requestId !== root.activeId) return
            root.busy = false
            root.activeId = -1
            root.error = message
            root.failure(status)
        }
    }
    Component.onDestruction: cancel()
}
