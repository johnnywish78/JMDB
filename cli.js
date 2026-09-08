#!/usr/bin/env node
const proc = require('child_process');
const e = require('./');
const c = proc.spawn(e, process.argv.slice(2), {stdio: 'inherit', windowsHide: false});
c.on('close', code => process.exit(code || 0));
