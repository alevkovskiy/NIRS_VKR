import QtQuick 2.0
import Sailfish.Silica 1.0

Label {
    x: Theme.horizontalPageMargin
    width: parent.width - 2 * x
    wrapMode: Text.Wrap
    textFormat: Text.PlainText
    color: Theme.highlightColor
    font.pixelSize: Theme.fontSizeSmall
    visible: text.length > 0
}
