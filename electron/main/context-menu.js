"use strict";
/** Shared context menu for web content (app UI + Browser Hub tabs). */
const { Menu, clipboard, shell } = require("electron");
const { truncate } = require("./url-utils");

function buildContextMenu(webContents, params, actions, options = {}) {
  const menu = Menu.buildFromTemplate(entries(webContents, params, actions, options));
  return menu;
}

function entries(webContents, params, actions, options) {
  const items = [];
  const { editFlags = {} } = params;

  if (params.linkURL) {
    items.push(
      {
        label: "Open link in new tab",
        click: () => actions.openTab(params.linkURL),
      },
      {
        label: "Open link in external browser",
        click: () => actions.openExternal(params.linkURL),
      },
      { type: "separator" },
      {
        label: "Copy link address",
        click: () => clipboard.writeText(params.linkURL),
      }
    );
  }

  if (params.mediaType === "image") {
    items.push(
      { type: "separator" },
      {
        label: "Open image in new tab",
        click: () => actions.openTab(params.srcURL),
      },
      {
        label: "Save image as…",
        click: () => webContents.downloadURL(params.srcURL),
      },
      {
        label: "Copy image address",
        click: () => clipboard.writeText(params.srcURL),
      }
    );
    if (params.hasImageContents) {
      items.push({
        label: "Copy image",
        click: () => webContents.copyImageAt(params.x, params.y),
      });
    }
  }

  if (params.isEditable) {
    items.push(
      { type: "separator" },
      { role: "cut", enabled: editFlags.canCut },
      { role: "copy", enabled: editFlags.canCopy },
      { role: "paste", enabled: editFlags.canPaste },
      { type: "separator" },
      { role: "selectAll", enabled: true }
    );
  } else if (params.selectionText) {
    items.push(
      { type: "separator" },
      { role: "copy", enabled: true },
      {
        label: `Search DuckDuckGo for “${truncate(params.selectionText, 24)}”`,
        click: () =>
          actions.openTab(
            "https://duckduckgo.com/?q=" + encodeURIComponent(params.selectionText)
          ),
      }
    );
  }

  if (options.hub) {
    items.push(
      { type: "separator" },
      {
        label: "Back",
        enabled: webContents.navigationHistory.canGoBack(),
        click: actions.back,
      },
      {
        label: "Forward",
        enabled: webContents.navigationHistory.canGoForward(),
        click: actions.forward,
      },
      {
        label: "Reload",
        accelerator: "CmdOrCtrl+R",
        click: actions.reload,
      },
      { type: "separator" },
      {
        label: "Zoom in",
        click: () => options.hubActions?.zoom("in"),
      },
      {
        label: "Zoom out",
        click: () => options.hubActions?.zoom("out"),
      },
      {
        label: "Actual size",
        click: () => options.hubActions?.zoom("reset"),
      }
    );
  } else if (options.appUi) {
    items.push(
      { type: "separator" },
      {
        label: "Back",
        enabled: webContents.navigationHistory.canGoBack(),
        click: actions.back,
      },
      {
        label: "Forward",
        enabled: webContents.navigationHistory.canGoForward(),
        click: actions.forward,
      },
      { label: "Reload page",
        accelerator: "CmdOrCtrl+R",
        click: actions.reload }
    );
  }

  if (actions.devtools) {
    items.push(
      { type: "separator" },
      {
        label: "Inspect element",
        click: () => webContents.inspectElement(params.x, params.y),
      }
    );
  }

  return items;
}

module.exports = { buildContextMenu };
