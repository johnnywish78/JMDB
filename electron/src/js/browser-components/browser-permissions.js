"use strict";

window.BrowserPermissions = {
  getLabel(permission) {
    const labels = {
      camera: "Camera",
      microphone: "Microphone",
      geolocation: "Location",
      notifications: "Notifications",
      "clipboard-read": "Clipboard Read",
      "clipboard-sanitized-write": "Clipboard Write",
      midi: "MIDI",
      "display-capture": "Screen Capture",
      fullscreen: "Fullscreen",
      pointerLock: "Pointer Lock",
      mediaKeySystem: "Media Key System",
      sensors: "Sensors",
      "serial-port": "Serial Port",
      "usb-device": "USB Device",
      "bluetooth-device": "Bluetooth Device",
      "hid-device": "HID Device",
      "window-management": "Window Management"
    };
    return labels[permission] || permission;
  }
};
