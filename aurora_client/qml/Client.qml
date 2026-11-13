import QtQuick 2.0
import Sailfish.Silica 1.0
import "pages"

ApplicationWindow {
    id: app
    initialPage: Component { LoginPage {} }
    allowedOrientations: Orientation.All
    cover: Component {
        CoverBackground {
            Label { anchors.centerIn: parent; text: "NIRS\n" + (Api.authenticated ? "Рабочее пространство" : "Вход"); horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; width: parent.width }
        }
    }
    Connections {
        target: Api
        onAuthenticatedChanged: {
            if (Api.authenticated) pageStack.replaceAbove(null, Qt.resolvedUrl("pages/HomePage.qml"))
            else pageStack.replaceAbove(null, Qt.resolvedUrl("pages/LoginPage.qml"))
        }
    }
}
