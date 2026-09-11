const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

test("Electron entry files exist", () => {
  assert.equal(
    fs.existsSync(path.join(__dirname, "..", "main.js")),
    true
  );

  assert.equal(
    fs.existsSync(path.join(__dirname, "..", "preload.js")),
    true
  );

  assert.equal(
    fs.existsSync(
      path.join(__dirname, "..", "src", "index.html")
    ),
    true
  );
});

test("preload does not enable renderer Node integration", () => {
  const source = fs.readFileSync(
    path.join(__dirname, "..", "main.js"),
    "utf8"
  );

  assert.match(source, /contextIsolation:\s*true/);
  assert.match(source, /nodeIntegration:\s*false/);
});
