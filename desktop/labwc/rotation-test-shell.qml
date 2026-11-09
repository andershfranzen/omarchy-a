import QtQuick
import Quickshell
import Quickshell.Wayland

// Isolated headless test fixture: deliberately recreate the bar before the
// wallpaper, reproducing a shell that rebuilds its layers during rotation.
Scope {
  id: root
  property var output: Quickshell.screens[0]
  property bool initialized: false
  Component.onCompleted: initialized = true
  Connections {
    target: root.output
    function onWidthChanged() {
      if (!root.initialized) return
      bar.visible = false
      background.visible = false
      popup.visible = false // a dismissed popup must never hold readiness
      barTimer.restart()
      backgroundTimer.restart()
    }
  }
  PanelWindow {
    id: popup
    screen: root.output
    anchors { right: true; top: true }
    margins.top: 60
    implicitWidth: 320
    implicitHeight: 150
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.namespace: "rotation-fixture-transient-popup"
    color: "#5a396c"
  }
  Timer { id: barTimer; interval: 60; onTriggered: bar.visible = true }
  Timer { id: backgroundTimer; interval: 450; onTriggered: background.visible = true }
  PanelWindow {
    id: background
    screen: root.output
    anchors { left: true; right: true; top: true; bottom: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Background
    WlrLayershell.namespace: "rotation-fixture-background"
    color: root.output.width > root.output.height ? "#234e70" : "#397638"
    Text { anchors.centerIn: parent; text: "BACKGROUND READY"; color: "white"; font.pixelSize: 32 }
  }
  PanelWindow {
    id: bar
    screen: root.output
    anchors { left: true; right: true; top: true }
    implicitHeight: 48
    exclusiveZone: 48
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.namespace: "rotation-fixture-bar"
    color: "#b54f35"
    Text { anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; text: "TOP LEFT"; color: "white"; font.pixelSize: 24 }
  }
}
