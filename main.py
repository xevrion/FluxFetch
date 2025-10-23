import sys
import os
import subprocess
import threading
import time
from urllib.parse import urlparse
import re

import requests
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QFileDialog, QSpinBox, QMessageBox
)

ARIA2_RPC_URL = "http://localhost:6800/jsonrpc"
ARIA2_RPC_SECRET = None  # set token if needed


class Aria2Controller:
    def __init__(self):
        self.proc = None

    def is_running(self):
        try:
            resp = requests.post(ARIA2_RPC_URL, json={"jsonrpc":"2.0","id":"q","method":"system.listMethods"})
            return resp.status_code == 200
        except Exception:
            return False

    def start_aria2(self, extra_args=None):
        if extra_args is None:
            extra_args = []
        if self.is_running():
            return True
        cmd = ['aria2c','--enable-rpc','--rpc-listen-all=false','--rpc-allow-origin-all',
               '--max-connection-per-server=8','--split=8','--continue=true','--daemon=false',
               '--rpc-listen-port=6800'] + extra_args
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(20):
                if self.is_running():
                    return True
                time.sleep(0.2)
            return self.is_running()
        except FileNotFoundError:
            return False

    def stop_aria2(self):
        if self.proc:
            self.proc.terminate()
            self.proc = None

    def add_uri(self, uri, options=None):
        payload = {"jsonrpc":"2.0","id":"q","method":"aria2.addUri","params":[[uri], options or {}]}
        resp = requests.post(ARIA2_RPC_URL, json=payload)
        return resp.json()

    def tell_status(self, gid):
        payload = {"jsonrpc":"2.0","id":"q","method":"aria2.tellStatus",
                   "params":[gid, ["status","completedLength","totalLength","downloadSpeed"]]}
        resp = requests.post(ARIA2_RPC_URL, json=payload)
        return resp.json()


class FallbackDownloader(QtCore.QObject):
    progress = QtCore.pyqtSignal(int)
    def __init__(self, url, dest):
        super().__init__()
        self.url = url
        self.dest = dest
        self._cancel = False
    def cancel(self):
        self._cancel = True
    def run(self):
        try:
            with requests.get(self.url, stream=True, timeout=15) as r:
                r.raise_for_status()
                total = int(r.headers.get('Content-Length', 0))
                downloaded = 0
                chunk_size = 1024*64
                with open(self.dest,'wb') as f:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if self._cancel: return
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            pct = int(downloaded*100/total) if total else 0
                            self.progress.emit(pct)
        except Exception as e:
            print('Download error:', e)


def get_direct_url(page_url):
    try:
        r = requests.get(page_url, timeout=10)
        if r.status_code != 200:
            return page_url
        m = re.search(r'window\.open\("([^"]+)"\)', r.text)
        if m:
            return m.group(1)
        return page_url
    except:
        return page_url


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Legal Download Manager (TXT only)")
        self.resize(900,600)

        self.aria = Aria2Controller()
        self.items = []
        self.active = []
        self.remaining = []

        central = QWidget()
        self.setCentralWidget(central)
        v = QVBoxLayout(central)

        # Top buttons
        h = QHBoxLayout()
        v.addLayout(h)
        self.open_file_btn = QPushButton("Open .txt with URLs")
        self.open_file_btn.clicked.connect(self.on_open_file)
        h.addWidget(self.open_file_btn)
        self.start_btn = QPushButton("Start Download (aria2 if available)")
        self.start_btn.clicked.connect(self.on_start)
        h.addWidget(self.start_btn)
        self.stop_btn = QPushButton("Stop All")
        self.stop_btn.clicked.connect(self.on_stop_all)
        h.addWidget(self.stop_btn)
        h.addStretch()

        # Parallel/connections
        h2 = QHBoxLayout()
        v.addLayout(h2)
        h2.addWidget(QLabel("Parallel downloads:"))
        self.parallel_spin = QSpinBox()
        self.parallel_spin.setValue(3)
        self.parallel_spin.setRange(1,16)
        h2.addWidget(self.parallel_spin)
        h2.addWidget(QLabel("Connections/file:"))
        self.conns_spin = QSpinBox()
        self.conns_spin.setValue(8)
        self.conns_spin.setRange(1,32)
        h2.addWidget(self.conns_spin)
        h2.addStretch()

        # Table
        self.table = QTableWidget(0,5)
        self.table.setHorizontalHeaderLabels(['','Filename','Size','Status','Progress'])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0,30)
        self.table.setColumnWidth(2,120)
        self.table.setColumnWidth(3,120)
        self.table.setColumnWidth(4,180)
        v.addWidget(self.table)

        # Poll timer
        self.poll_timer = QtCore.QTimer()
        self.poll_timer.setInterval(1000)
        self.poll_timer.timeout.connect(self.poll_status)

    def on_open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open URL list", "", "Text files (*.txt);;All files (*)")
        if not path: return
        with open(path,'r',encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
        if not urls:
            QMessageBox.information(self,"No URLs","No URLs found in the selected file")
            return
        self.populate_table(urls)

    def populate_table(self, urls):
        self.table.setRowCount(0)
        self.items = []
        for url in urls:
            row = self.table.rowCount()
            self.table.insertRow(row)
            chk = QtWidgets.QCheckBox()
            chk.setChecked(True)
            self.table.setCellWidget(row,0,chk)
            fn = os.path.basename(urlparse(url).path) or url
            self.table.setItem(row,1,QTableWidgetItem(fn))
            size_item = QTableWidgetItem("—")
            self.table.setItem(row,2,size_item)
            status_item = QTableWidgetItem("queued")
            self.table.setItem(row,3,status_item)
            prog = QProgressBar()
            prog.setValue(0)
            self.table.setCellWidget(row,4,prog)
            self.items.append({'url':url,'filename':fn,'row':row,'size_item':size_item,'status_item':status_item,'progress':prog,'aria_gid':None,'download_thread':None})
        threading.Thread(target=self._populate_sizes, daemon=True).start()

    def _populate_sizes(self):
        for it in self.items:
            try:
                r = requests.head(it['url'], allow_redirects=True, timeout=8)
                if r.status_code==200 and 'Content-Length' in r.headers:
                    it['size_item'].setText(self._human_size(int(r.headers['Content-Length'])))
            except: pass

    def _human_size(self,n):
        for unit in ['B','KB','MB','GB','TB']:
            if n<1024: return f"{n:.1f}{unit}"
            n/=1024
        return f"{n:.1f}PB"

    def on_start(self):
        conns = self.conns_spin.value()
        parallel = self.parallel_spin.value()
        aria_started = self.aria.start_aria2(extra_args=[f'--max-connection-per-server={conns}',f'--split={conns}',f'--max-concurrent-downloads={parallel}'])
        if aria_started:
            print("aria2 started")
        else:
            QMessageBox.information(self,"aria2 not found","aria2 not found. Falling back to internal downloader.")

        dest_dir = QFileDialog.getExistingDirectory(self,"Choose download directory")
        if not dest_dir: return
        self.last_dest_dir = dest_dir

        selected = [it for it in self.items if self.table.cellWidget(it['row'],0).isChecked()]
        if not selected: return

        for it in selected:
            it['status_item'].setText('resolving link...')
            QtWidgets.QApplication.processEvents()
            it['url'] = get_direct_url(it['url'])
            it['status_item'].setText('queued')

        self.remaining = selected.copy()
        self.active = []
        self.parallel = parallel
        self.poll_timer.start()
        for _ in range(min(self.parallel,len(self.remaining))):
            self._start_next()

    def _start_next(self):
        if not self.remaining: return
        it = self.remaining.pop(0)
        url = it['url']
        dest_dir = getattr(self,'last_dest_dir',os.getcwd())
        it['status_item'].setText('starting')
        if self.aria.is_running():
            options = {'dir':dest_dir,'split':str(self.conns_spin.value()),'max-connection-per-server':str(self.conns_spin.value())}
            try:
                res = self.aria.add_uri(url, options=options)
                it['aria_gid'] = res.get('result')
                it['status_item'].setText('downloading')
            except:
                it['status_item'].setText('error')
        else:
            dest = os.path.join(dest_dir,it['filename'])
            fd = FallbackDownloader(url,dest)
            fd.progress.connect(lambda p,it=it: it['progress'].setValue(p))
            th = threading.Thread(target=fd.run,daemon=True)
            it['download_thread'] = {'thread':th,'fd':fd}
            it['status_item'].setText('downloading')
            th.start()
        self.active.append(it)

    def on_stop_all(self):
        try: self.aria.stop_aria2()
        except: pass
        for it in self.items:
            dt = it.get('download_thread')
            if dt: dt.get('fd').cancel(); it['status_item'].setText('cancelled')
        self.poll_timer.stop()

    def poll_status(self):
        if self.aria.is_running():
            for it in list(self.active):
                gid = it.get('aria_gid')
                if not gid: continue
                try:
                    r = self.aria.tell_status(gid)
                    res = r.get('result')
                    if not res: continue
                    total = int(res.get('totalLength',0))
                    done = int(res.get('completedLength',0))
                    speed = int(res.get('downloadSpeed',0))
                    pct = int(done*100/total) if total else 0
                    it['progress'].setValue(pct)
                    if res.get('status')=='complete':
                        it['status_item'].setText('complete')
                        self.active.remove(it)
                        self._start_next()
                    elif res.get('status')=='error':
                        it['status_item'].setText('error')
                        self.active.remove(it)
                        self._start_next()
                    else:
                        it['status_item'].setText(f"{res.get('status')} @ {self._human_size(speed)}/s")
                except: pass
        else:
            for it in list(self.active):
                dt = it.get('download_thread')
                if dt:
                    th = dt.get('thread')
                    if not th.is_alive():
                        it['status_item'].setText('complete')
                        it['progress'].setValue(100)
                        self.active.remove(it)
                        self._start_next()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
