import QtQuick 2.0
import Sailfish.Silica 1.0

Column {
    id: root
    property var rows: []
    width: parent.width
    spacing: Theme.paddingSmall
    Repeater {
        model: root.rows
        Column {
            x: Theme.horizontalPageMargin
            width: root.width - 2 * x
            Label { text: modelData[0]; color: Theme.secondaryColor; font.pixelSize: Theme.fontSizeSmall }
            Label { width: parent.width; text: String(modelData[1] === null || modelData[1] === undefined ? "—" : modelData[1]); textFormat: Text.PlainText; wrapMode: Text.Wrap }
        }
    }
}
