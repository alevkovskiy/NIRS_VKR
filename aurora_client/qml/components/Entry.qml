import QtQuick 2.0
import Sailfish.Silica 1.0

BackgroundItem {
    id: root
    property string title: ""
    property string subtitle: ""
    height: column.height + 2 * Theme.paddingMedium
    Column {
        id: column
        x: Theme.horizontalPageMargin
        y: Theme.paddingMedium
        width: parent.width - 2 * x
        spacing: Theme.paddingSmall
        Label {
            width: parent.width
            text: root.title
            textFormat: Text.PlainText
            color: root.highlighted ? Theme.highlightColor : Theme.primaryColor
            wrapMode: Text.Wrap
        }
        Label {
            width: parent.width
            text: root.subtitle
            textFormat: Text.PlainText
            color: Theme.secondaryColor
            font.pixelSize: Theme.fontSizeSmall
            wrapMode: Text.Wrap
            visible: text.length > 0
        }
    }
}
