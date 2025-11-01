# -*- coding: utf-8 -*-
"""
Postman2Repeater - Burp Suite Extension (Jython 2.7)

Features
- Load a Postman collection (v2.x JSON) and an environment JSON.
- Resolve {{variables}} from the loaded environment and collection variables.
- List all requests in a table (name, method, URL).
- Send selected or all requests directly to Burp Repeater, one tab per request.

Usage
1) In Burp, Extender → Options → Python Environment → set Jython standalone jar.
2) Extender → Extensions → Add → Extension type: Python → select this file.
3) Open the new tab “Postman2Repeater”.
4) Click “Load Collection...” (select .json), then “Load Environment...” (optional).
5) Select a row → “Send Selected to Repeater” or use “Send All to Repeater”.

Notes / Limitations
- Supports Postman body modes: raw and urlencoded. Others are best-effort (sent as raw when possible).
- Headers in the Postman item are honored (disabled headers are skipped). Host header is auto-set from URL.
- URL variables and raw strings with {{var}} are substituted from (environment ⟶ collection vars).
- If a URL lacks a path, "/" is used. If a port is not specified, defaults are 80 (http) / 443 (https).

Tested on: Burp Suite Professional 2023.x–2025.x with Jython 2.7.3

Author: cdogu
License: MIT
"""

from burp import IBurpExtender, ITab
from java.awt import BorderLayout, Dimension
from java.awt.event import ActionListener
from javax.swing import (
    JPanel, JButton, JLabel, JFileChooser, JScrollPane, JTable, JOptionPane,
    BoxLayout, JTextField, JCheckBox, Box
)
from javax.swing.table import DefaultTableModel
from java.net import URL
from java.lang import String
import re

# Jython stdlib json is available
import json

class BurpExtender(IBurpExtender, ITab, ActionListener):
    def registerExtenderCallbacks(self, callbacks):
        self.callbacks = callbacks
        self.helpers = callbacks.getHelpers()
        callbacks.setExtensionName("Postman2Repeater")

        # Data holders
        self.collection = None
        self.collection_name = ""
        self.environment = {}
        self.collection_vars = {}
        self.items = []  # flattened list of dicts: {name, method, url_raw, postman_req}

        # UI
        self._tab = JPanel(BorderLayout())
        self._tab.setPreferredSize(Dimension(900, 500))

        # Top controls
        top = JPanel()
        top.setLayout(BoxLayout(top, BoxLayout.X_AXIS))

        self.lblCollection = JLabel("Collection: (not loaded)")
        self.btnLoadCollection = JButton("Load Collection...", actionCommand="load_collection")
        self.btnLoadCollection.addActionListener(self)

        self.lblEnv = JLabel("Environment: (not loaded)")
        self.btnLoadEnv = JButton("Load Environment...", actionCommand="load_env")
        self.btnLoadEnv.addActionListener(self)

        self.chkAutoVar = JCheckBox("Substitute {{vars}}", True)

        top.add(self.btnLoadCollection)
        top.add(Box.createHorizontalStrut(8))
        top.add(self.lblCollection)
        top.add(Box.createHorizontalStrut(20))
        top.add(self.btnLoadEnv)
        top.add(Box.createHorizontalStrut(8))
        top.add(self.lblEnv)
        top.add(Box.createHorizontalGlue())
        top.add(self.chkAutoVar)

        # Table
        self.tableModel = DefaultTableModel(["Name", "Method", "URL"], 0)
        self.table = JTable(self.tableModel)
        self.table.setAutoCreateRowSorter(True)
        scroll = JScrollPane(self.table)

        # Bottom controls
        bottom = JPanel()
        bottom.setLayout(BoxLayout(bottom, BoxLayout.X_AXIS))
        self.btnSendSelected = JButton("Send Selected to Repeater", actionCommand="send_selected")
        self.btnSendSelected.addActionListener(self)

        self.btnSendAll = JButton("Send All to Repeater", actionCommand="send_all")
        self.btnSendAll.addActionListener(self)

        bottom.add(self.btnSendSelected)
        bottom.add(Box.createHorizontalStrut(12))
        bottom.add(self.btnSendAll)
        bottom.add(Box.createHorizontalGlue())

        self._tab.add(top, BorderLayout.NORTH)
        self._tab.add(scroll, BorderLayout.CENTER)
        self._tab.add(bottom, BorderLayout.SOUTH)

        callbacks.addSuiteTab(self)

    # ITab
    def getTabCaption(self):
        return "Postman2Repeater"

    def getUiComponent(self):
        return self._tab

    # --- injected safety shims: ensure these helpers exist inside the class ---
    def _error(self, msg):
        try:
            JOptionPane.showMessageDialog(self._tab, String(msg))
        except Exception:
            try:
                print(msg)
            except Exception:
                pass

    def _subst(self, text):
        if text is None:
            return text
        # Lazy-compile pattern
        if not hasattr(self, '_var_pat') or self._var_pat is None:
            self._var_pat = re.compile(r"{{\s*([^}]+?)\s*}}")
        lookup = {}
        if getattr(self, 'collection_vars', None):
            lookup.update(self.collection_vars)
        if getattr(self, 'environment', None):
            lookup.update(self.environment)
        def repl(m):
            key = m.group(1)
            return lookup.get(key, m.group(0))
        try:
            return self._var_pat.sub(repl, text)
        except Exception:
            return text
        # Lazy-compile pattern
        if not hasattr(self, '_var_pat') or self._var_pat is None:
            self._var_pat = re.compile(r"{{\s*([^}]+?)\s*}}")
        lookup = {}
        if getattr(self, 'collection_vars', None):
            lookup.update(self.collection_vars)
        if getattr(self, 'environment', None):
            lookup.update(self.environment)
        def repl(m):
            key = m.group(1)
            return lookup.get(key, m.group(0))
        try:
            return self._var_pat.sub(repl, text)
        except Exception:
            return text

    # Actions
    def actionPerformed(self, e):
        cmd = e.getActionCommand()
        if cmd == "load_collection":
            self.load_collection_dialog()
        elif cmd == "load_env":
            self.load_env_dialog()
        elif cmd == "send_selected":
            self.send_selected()
        elif cmd == "send_all":
            self.send_all()

    # File loaders
    def load_collection_dialog(self):
        chooser = JFileChooser()
        if chooser.showOpenDialog(self._tab) == JFileChooser.APPROVE_OPTION:
            f = chooser.getSelectedFile()
            try:
                with open(f.getAbsolutePath(), 'rb') as fh:
                    data = fh.read()
                self.collection = json.loads(data)
                self.collection_name = self.collection.get('info', {}).get('name', f.getName())
                # collection-level variables
                self.collection_vars = {}
                for v in self.collection.get('variable', []) or []:
                    key = v.get('key') or v.get('id')
                    val = v.get('value')
                    if key is not None and val is not None:
                        self.collection_vars[str(key)] = str(val)
                # flatten items
                self.items = []
                root_items = self.collection.get('item', []) or []
                self._flatten_items(root_items, [])
                # populate table
                self._refresh_table()
                self.lblCollection.setText("Collection: %s" % self.collection_name)
                JOptionPane.showMessageDialog(self._tab, "Loaded %d requests" % len(self.items))
            except Exception as ex:
                self._error("Failed to load collection: %s" % ex)

    def load_env_dialog(self):
        chooser = JFileChooser()
        if chooser.showOpenDialog(self._tab) == JFileChooser.APPROVE_OPTION:
            f = chooser.getSelectedFile()
            try:
                with open(f.getAbsolutePath(), 'rb') as fh:
                    data = fh.read()
                js = json.loads(data)
                env_map = {}
                # Postman environment v2: {"values": [{key, value, enabled}]}
                for v in js.get('values', []) or []:
                    if v.get('enabled', True) and v.get('key') is not None:
                        env_map[str(v['key'])] = str(v.get('value', ''))
                self.environment = env_map
                self.lblEnv.setText("Environment: %s (%d vars)" % (getattr(f, 'getName', lambda: 'env.json')(), len(env_map)))
                JOptionPane.showMessageDialog(self._tab, "Loaded %d environment variables" % len(env_map))
            except Exception as ex:
                self._error("Failed to load environment: %s" % ex)

    # Helpers to flatten and display items
    def _flatten_items(self, items, path):
        for it in items:
            name = it.get('name', 'unnamed')
            if 'item' in it and isinstance(it['item'], list):
                self._flatten_items(it['item'], path + [name])
            else:
                req = it.get('request', {})
                if not req:
                    continue
                method = (req.get('method') or 'GET').upper()
                url = req.get('url')
                url_raw = None
                if isinstance(url, basestring):
                    url_raw = url
                elif isinstance(url, dict):
                    url_raw = url.get('raw') or self._url_from_parts(url)
                else:
                    continue
                self.items.append({
                    'name': ' / '.join(path + [name]),
                    'method': method,
                    'url_raw': url_raw,
                    'postman_req': req
                })

    def _url_from_parts(self, u):
        # Fallback builder: tries to assemble from protocol/host/path/query
        scheme = u.get('protocol') or 'http'
        host = ''
        if isinstance(u.get('host'), list):
            host = '.'.join([x for x in u['host'] if x])
        elif isinstance(u.get('host'), basestring):
            host = u['host']
        path = ''
        if isinstance(u.get('path'), list):
            path = '/' + '/'.join([x for x in u['path'] if x])
        elif isinstance(u.get('path'), basestring):
            path = '/' + u['path'].lstrip('/')
        query = ''
        if isinstance(u.get('query'), list) and u['query']:
            qparts = []
            for q in u['query']:
                if q.get('disabled'): continue
                k = q.get('key') or ''
                v = q.get('value') or ''
                qparts.append('%s=%s' % (k, v))
            if qparts:
                query = '?' + '&'.join(qparts)
        return '%s://%s%s%s' % (scheme, host, path or '/', query)

    def _refresh_table(self):
        # Clear
        while self.tableModel.getRowCount() > 0:
            self.tableModel.removeRow(0)
        # Fill
        for it in self.items:
            url_disp = it['url_raw'] or ''
            self.tableModel.addRow([it['name'], it['method'], url_disp])

    # Sender logic
    def send_selected(self):
        row = self.table.getSelectedRow()
        if row < 0:
            JOptionPane.showMessageDialog(self._tab, "Select a row first.")
            return
        viewRow = row
        modelRow = self.table.convertRowIndexToModel(viewRow)
        it = self.items[modelRow]
        self._send_item_to_repeater(it)

    def send_all(self):
        count = 0
        for it in self.items:
            try:
                self._send_item_to_repeater(it)
                count += 1
            except Exception as ex:
                self._error("Failed to send '%s': %s" % (it.get('name'), ex))
        JOptionPane.showMessageDialog(self._tab, "Queued %d requests to Repeater" % count)

    def _send_item_to_repeater(self, it):
        # Build HTTP message
        name = it['name']
        method = it['method']
        url_str = it['url_raw']
        if self.chkAutoVar.isSelected():
            url_str = self._subst(url_str)
        jurl = URL(url_str)

        scheme = jurl.getProtocol().lower()
        host = jurl.getHost()
        port = jurl.getPort()
        if port == -1:
            port = 443 if scheme == 'https' else 80
        use_https = (scheme == 'https')

        # Path + query
        path = jurl.getPath()
        if not path:
            path = "/"
        query = jurl.getQuery()
        if query:
            path_q = path + "?" + query
        else:
            path_q = path

        # Headers from Postman
        headers = []
        # Mandatory Host
        default_host = host if ((port == 80 and not use_https) or (port == 443 and use_https)) else ("%s:%d" % (host, port))
        headers.append("Host: %s" % default_host)
        # Add user-specified headers
        pm_req = it['postman_req']
        for h in (pm_req.get('header') or []):
            if h.get('disabled'): continue
            k = h.get('key')
            v = h.get('value')
            if not k:
                continue
            hv = ("%s: %s" % (k, v or ""))
            if self.chkAutoVar.isSelected():
                hv = self._subst(hv)
            # Avoid duplicate Host since we set it above
            if hv.lower().startswith('host:'):
                continue
            headers.append(hv)

        body_bytes = None
        content_type_present = any(h.lower().startswith('content-type:') for h in [x.lower() for x in headers])

        # Body handling
        body = pm_req.get('body') or {}
        mode = (body.get('mode') or '').lower()
        if mode == 'raw':
            raw = body.get('raw') or ''
            if self.chkAutoVar.isSelected():
                raw = self._subst(raw)
            body_bytes = String(raw).getBytes('UTF-8')
            # Add a default content-type if missing
            if not content_type_present and raw:
                headers.append('Content-Type: text/plain; charset=UTF-8')
        elif mode == 'urlencoded':
            parts = []
            for p in (body.get('urlencoded') or []):
                if p.get('disabled'): continue
                k = p.get('key') or ''
                v = p.get('value') or ''
                kv = '%s=%s' % (k, v)
                if self.chkAutoVar.isSelected():
                    kv = self._subst(kv)
                parts.append(kv)
            enc = '&'.join(parts)
            body_bytes = String(enc).getBytes('UTF-8')
            if not content_type_present:
                headers.append('Content-Type: application/x-www-form-urlencoded')
        elif mode == 'formdata':
            # Best-effort: send as simple multipart-like text (not full multipart builder)
            boundary = '----p2rBoundary'
            lines = []
            for p in (body.get('formdata') or []):
                if p.get('disabled'): continue
                name = p.get('key') or 'file'
                val = p.get('value') or ''
                if self.chkAutoVar.isSelected():
                    val = self._subst(val)
                lines.append('--' + boundary)
                lines.append('Content-Disposition: form-data; name="%s"' % name)
                lines.append('')
                lines.append(val)
            lines.append('--' + boundary + '--')
            raw = '\r\n'.join(lines)
            body_bytes = String(raw).getBytes('UTF-8')
            if not content_type_present:
                headers.append('Content-Type: multipart/form-data; boundary=%s' % boundary)
        else:
            # No/unknown body mode
            body_bytes = None

        # Content-Length: let Burp compute it via buildHttpMessage
        if body_bytes is None:
            body_bytes = self.helpers.stringToBytes("")

        # Default Connection header
        if not any(h.lower().startswith('connection:') for h in [x.lower() for x in headers]):
            headers.append('Connection: close')

        # Build final request via Burp helpers (handles CRLF and Content-Length)
        all_headers = ["%s %s HTTP/1.1" % (method, path_q)]
        # Remove any Content-Length we might have added earlier (defensive)
        all_headers.extend([h for h in headers if not h.lower().startswith("content-length:")])

        req_bytes = self.helpers.buildHttpMessage(all_headers, body_bytes)

        tab_name = (self.collection_name or 'Postman') + ' - ' + (name or method)
        try:
            self.callbacks.sendToRepeater(host, port, use_https, req_bytes, tab_name)
        except Exception as ex:
            self._error("sendToRepeater failed: %s" % ex)
