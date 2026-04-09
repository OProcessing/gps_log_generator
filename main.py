# -*- coding: utf-8 -*-
"""
GPS 로그 생성기 – 업무 보조용 PyQt5 UI.
- DB 로드 및 FLAG 비트 필터(정의된 플래그 체크박스)
- 선택한 DB 지점을 **지나는** 주행 로그 생성(기준점 + 시작/종료 거리)
- 지도에 구간 표시
"""
import math
import os
import json
import sys
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QSpinBox,
    QDoubleSpinBox,
    QFileDialog,
    QMessageBox,
    QHeaderView,
    QAbstractItemView,
    QFormLayout,
    QCheckBox,
    QSplitter,
    QScrollArea,
    QFrame,
    QGridLayout,
    QMenuBar,
    QMenu,
    QAction,
    QStatusBar,
    QSizePolicy,
    QComboBox,
    QInputDialog,
    QLineEdit,
)
from PyQt5.QtCore import Qt, QUrl, QRect, QThread, pyqtSignal, QTimer, QObject, pyqtSlot
from PyQt5.QtGui import QFont

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
    from PyQt5.QtWebChannel import QWebChannel
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

from gps_log_generator_app import gps_log_generator as gps
from gps_log_generator_app.db_parser import load_db, get_numeric
from gps_log_generator_app.flag_defs import FLAG_DEFINITIONS, flag_mask_from_indices
from gps_log_generator_app.geo_utils import start_end_from_reference
from gps_log_generator_app.favorites import load_favorites, save_favorites
from gps_log_generator_app.runtime_paths import get_runtime_root


COL_IDX = "IDX"
COL_X = "X"   # DB에서는 경도(Lon)
COL_Y = "Y"   # DB에서는 위도(Lat)
COL_FLAG = "FLAG"
COL_SPEED = "SPEED"
COL_DIRECTION = "DIRECTION"

# 테이블에 표시할 컬럼 (DB키, 표시이름). 순서: 위도, 경도, 방향, 제한속도, 플래그, 지역, 스크린네임
TABLE_DISPLAY_COLUMNS = [
    ("Y", "위도"),
    ("X", "경도"),
    ("DIRECTION", "방향"),
    ("SPEED", "제한속도"),
    ("FLAG", "플래그"),
    ("REGION", "지역"),
    ("SCREENNAME", "스크린네임"),
]

# 모스크바 크렘린궁 (지도 초기 위치 및 기준점 기본값)
DEFAULT_REF_LAT = 55.7520
DEFAULT_REF_LON = 37.6175
# 지도 초기 줌 (0=전세계 ~ 18=가장 상세, 숫자 클수록 해상도 높음)
DEFAULT_MAP_ZOOM = 16

POINTS_PER_KM = 80
MIN_POINTS = 50
MAX_POINTS = 3000

# db 폴더(기본 DB). 실행 위치와 무관하게 찾기 위해 후보 경로 사용
PROJECT_ROOT = get_runtime_root()
def _find_db_dir() -> Path | None:
    exe_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None
    for candidate in [
        *( [exe_dir / "db"] if exe_dir is not None else [] ),
        PROJECT_ROOT / "db",
        Path.cwd() / "db",
        Path.cwd() / "gps_log_generator" / "db",
    ]:
        if candidate.is_dir():
            return candidate
    return None


CHUNK_SIZE = 500
DEFAULT_FILTER_RADIUS_KM = 5
MIN_FILTER_RADIUS_KM = 1
MAX_FILTER_RADIUS_KM = 30
FILTER_RADIUS_STEP_KM = 1
SPATIAL_CELL_DEG = 0.05
FILTER_DEBOUNCE_MS = 220
SEARCH_EXPAND_THRESHOLD = 100
MAX_START_DIST_M = 3000.0
MAX_END_DIST_M = 1000.0


class DBLoaderThread(QThread):
    """백그라운드에서 DB 파일 청크 로드. db_loaded(path, rows) 시그널."""
    db_loaded = pyqtSignal(str, list)

    def __init__(self, file_path: str, limit: int | None = None, offset: int = 0, parent=None):
        super().__init__(parent)
        self._file_path = file_path
        self._limit = limit
        self._offset = offset

    def run(self):
        rows = load_db(self._file_path, limit=self._limit, offset=self._offset)
        self.db_loaded.emit(self._file_path, rows)


def _make_map_html() -> str:
    zoom = DEFAULT_MAP_ZOOM
    return f"""<!DOCTYPE html>
<html style="height:100%;">
<head>
  <meta charset="utf-8" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
  <style>
    html, body {{ height: 100%; margin: 0; padding: 0; }} #map {{ width: 100%; height: 100%; }}
    .pin-num {{ background:#0066cc; color:#fff; border:2px solid #fff; border-radius:50%; width:28px; height:28px; line-height:24px; text-align:center; font-weight:bold; font-size:14px; box-shadow:0 1px 4px rgba(0,0,0,0.4); }}
    .pin-num.start {{ background:#2e7d32; }}
    .pin-num.ref {{ background:#1565c0; }}
    .pin-num.end {{ background:#c62828; }}
    .db-pin {{
      position: relative;
      width: 14px;
      height: 14px;
      background: #e53935;
      border: 2px solid #fff;
      border-radius: 50% 50% 50% 0;
      box-shadow: 0 1px 4px rgba(0,0,0,0.45);
      transform: rotate(-45deg);
    }}
    .db-pin:after {{
      content: '';
      position: absolute;
      width: 4px;
      height: 4px;
      top: 3px;
      left: 3px;
      border-radius: 50%;
      background: #ffffff;
    }}
    .db-pin.active {{
      width: 21px;
      height: 21px;
      background: #b71c1c;
      border-color: #fff176;
      box-shadow: 0 0 0 2px rgba(255, 241, 118, 0.35), 0 2px 9px rgba(0,0,0,0.65);
    }}
    .db-pin.active:after {{
      width: 6px;
      height: 6px;
      top: 5px;
      left: 5px;
      background: #fffde7;
    }}
  </style>
</head>
<body style="margin:0; padding:0; height:100%;">
  <div id="map" style="position:absolute; left:0; top:0; right:0; bottom:0;"></div>
  <script>
    var map = L.map('map').setView([55.7520, 37.6175], {zoom});
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; OpenStreetMap'
    }}).addTo(map);
    var refMarker = null;
    var startMarker = null;
    var endMarker = null;
    var line = null;
    var nearbyLayer = L.layerGroup().addTo(map);
    var nearbyPin = null;
    var nearbyPinActive = null;
    var activeNearbyMarker = null;
    var lockedNearbyMarker = null;
    var bridge = null;
    if (typeof QWebChannel !== 'undefined' && typeof qt !== 'undefined' && qt.webChannelTransport) {{
      new QWebChannel(qt.webChannelTransport, function(channel) {{
        bridge = channel.objects.bridge;
      }});
    }}
    function pinIcon(num, cls) {{
      return L.divIcon({{ className: 'pin-num-wrap', html: '<div class="pin-num ' + cls + '">' + num + '</div>', iconSize: [28, 28], iconAnchor: [14, 14] }});
    }}
    function nearbyPinIcon() {{
      if (!nearbyPin) {{
        nearbyPin = L.divIcon({{
          className: 'db-pin-wrap',
          html: '<div class="db-pin"></div>',
          iconSize: [18, 18],
          iconAnchor: [6, 16]
        }});
      }}
      return nearbyPin;
    }}
    function nearbyPinActiveIcon() {{
      if (!nearbyPinActive) {{
        nearbyPinActive = L.divIcon({{
          className: 'db-pin-wrap active',
          html: '<div class="db-pin active"></div>',
          iconSize: [26, 26],
          iconAnchor: [10, 22]
        }});
      }}
      return nearbyPinActive;
    }}
    function setActiveNearbyMarker(marker) {{
      if (activeNearbyMarker && activeNearbyMarker !== marker) {{
        activeNearbyMarker.setIcon(nearbyPinIcon());
      }}
      activeNearbyMarker = marker;
      if (activeNearbyMarker) {{
        activeNearbyMarker.setIcon(nearbyPinActiveIcon());
      }}
    }}
    function clearActiveNearbyMarker() {{
      if (lockedNearbyMarker) return;
      if (activeNearbyMarker) {{
        activeNearbyMarker.setIcon(nearbyPinIcon());
      }}
      activeNearbyMarker = null;
    }}
    map.on('click', function() {{
      lockedNearbyMarker = null;
      clearActiveNearbyMarker();
    }});
    function updateLineFromMarkers() {{
      if (!line || !startMarker || !refMarker || !endMarker) return;
      line.setLatLngs([startMarker.getLatLng(), refMarker.getLatLng(), endMarker.getLatLng()]);
    }}
    function notifyRouteMoved() {{
      if (!bridge || typeof bridge.routeMoved !== 'function' || !refMarker || !startMarker || !endMarker) return;
      var r = refMarker.getLatLng();
      var s = startMarker.getLatLng();
      var e = endMarker.getLatLng();
      bridge.routeMoved(r.lat, r.lng, s.lat, s.lng, e.lat, e.lng);
    }}
    function bindDraggableHandlers(marker) {{
      marker.on('drag', function() {{ updateLineFromMarkers(); }});
      marker.on('dragend', function() {{
        updateLineFromMarkers();
        notifyRouteMoved();
      }});
    }}
    function updateRoute(refLat, refLon, startLat, startLon, endLat, endLon) {{
      if (refMarker) map.removeLayer(refMarker);
      if (startMarker) map.removeLayer(startMarker);
      if (endMarker) map.removeLayer(endMarker);
      if (line) map.removeLayer(line);
      startMarker = L.marker([startLat, startLon], {{ icon: pinIcon('1', 'start'), draggable: true }}).addTo(map).bindPopup('1. 시작');
      refMarker = L.marker([refLat, refLon], {{ icon: pinIcon('2', 'ref'), draggable: true }}).addTo(map).bindPopup('2. 기준점');
      endMarker = L.marker([endLat, endLon], {{ icon: pinIcon('3', 'end'), draggable: true }}).addTo(map).bindPopup('3. 종료');
      line = L.polyline([[startLat, startLon], [refLat, refLon], [endLat, endLon]], {{ color: '#0066cc', weight: 4 }}).addTo(map);
      bindDraggableHandlers(startMarker);
      bindDraggableHandlers(refMarker);
      bindDraggableHandlers(endMarker);
      map.fitBounds(line.getBounds(), {{ padding: [30, 30] }});
    }}
    function setNearbyPoints(points) {{
      nearbyLayer.clearLayers();
      activeNearbyMarker = null;
      lockedNearbyMarker = null;
      if (!points || !Array.isArray(points)) return;
      for (var i = 0; i < points.length; i += 1) {{
        var p = points[i];
        var m = L.marker([p.lat, p.lon], {{
          icon: nearbyPinIcon(),
          keyboard: false
        }}).addTo(nearbyLayer);
        if (bridge && typeof bridge.nearbyHovered === 'function' && typeof p.row === 'number') {{
          m.on('mouseover', (function(rowIdx) {{
            return function() {{
              if (lockedNearbyMarker) return;
              setActiveNearbyMarker(this);
              bridge.nearbyHovered(rowIdx);
            }};
          }})(p.row));
          m.on('mouseout', function() {{
            if (!lockedNearbyMarker) {{
              clearActiveNearbyMarker();
            }}
          }});
          m.on('click', (function(rowIdx) {{
            return function(e) {{
              L.DomEvent.stopPropagation(e);
              lockedNearbyMarker = this;
              setActiveNearbyMarker(this);
              bridge.nearbyHovered(rowIdx);
            }};
          }})(p.row));
        }}
      }}
    }}
  </script>
</body>
</html>"""


class OSMInterceptor(QWebEngineUrlRequestInterceptor if HAS_WEBENGINE else object):
    def interceptRequest(self, info):
        info.setHttpHeader(b"Accept-Language", b"en-US,en;q=0.9")


class MapBridge(QObject):
    route_changed = pyqtSignal(float, float, float, float, float, float)
    nearby_hovered = pyqtSignal(int)

    @pyqtSlot(float, float, float, float, float, float)
    def routeMoved(
        self,
        ref_lat: float,
        ref_lon: float,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
    ):
        self.route_changed.emit(ref_lat, ref_lon, start_lat, start_lon, end_lat, end_lon)

    @pyqtSlot(int)
    def nearbyHovered(self, table_row: int):
        self.nearby_hovered.emit(table_row)


class MapAspectWidget(QWidget):
    """지도 뷰를 1:1 비율로 유지."""
    ASPECT_W = 1
    ASPECT_H = 1

    def __init__(self, map_view: "QWebEngineView", parent=None):
        super().__init__(parent)
        self._map_view = map_view
        self._map_view.setParent(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = event.size().width(), event.size().height()
        if h <= 0:
            return
        if w / h > self.ASPECT_W / self.ASPECT_H:
            fit_w = int(h * self.ASPECT_W / self.ASPECT_H)
            x = (w - fit_w) // 2
            self._map_view.setGeometry(QRect(x, 0, fit_w, h))
        else:
            fit_h = int(w * self.ASPECT_H / self.ASPECT_W)
            y = (h - fit_h) // 2
            self._map_view.setGeometry(QRect(0, y, w, fit_h))


class GpsLogGeneratorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._db_path = ""
        self._db_rows = []
        self._filtered_rows = []
        self._filtered_indices: list[int] = []
        self._row_coords: list[tuple[float, float] | None] = []
        self._spatial_index: dict[tuple[int, int], list[int]] = {}
        self._ref_speed: float | None = None
        self._db_loader: DBLoaderThread | None = None
        self._favorites: list[dict] = []
        self._default_db_load_done = False
        self._db_has_more = True
        self._is_updating_from_map = False
        self._custom_route_override: tuple[float, float, float, float, float, float] | None = None
        self._filter_debounce_timer = QTimer(self)
        self._filter_debounce_timer.setSingleShot(True)
        self._filter_debounce_timer.timeout.connect(self._apply_filter_internal)
        self.setWindowTitle("GPS 로그 생성기")
        self.setMinimumSize(1280, 820)
        self.resize(1520, 960)
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 메뉴
        menubar = self.menuBar()
        file_menu = menubar.addMenu("파일(&F)")
        open_act = QAction("DB 파일 열기(&O)...", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self._on_open_db)
        file_menu.addAction(open_act)
        file_menu.addSeparator()
        exit_act = QAction("종료(&X)", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("DB 로딩 중…")

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)

        # 왼쪽: DB + 필터 + 테이블 + 생성 파라미터
        left = QWidget()
        left.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left.setMinimumWidth(460)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # DB 파일
        db_group = QGroupBox("DB 데이터")
        db_layout = QVBoxLayout(db_group)
        row1 = QHBoxLayout()
        self._btn_open = QPushButton("DB 파일 열기")
        self._btn_open.clicked.connect(self._on_open_db)
        self._label_file = QLabel("(파일 미선택)")
        self._label_file.setStyleSheet("color: #666;")
        row1.addWidget(self._btn_open)
        row1.addWidget(self._label_file)
        row1.addStretch()
        db_layout.addLayout(row1)

        # FLAG 필터 (정의된 플래그 체크박스)
        flag_label = QLabel("FLAG 필터 (해당 비트가 모두 포함된 행만 표시)")
        flag_label.setStyleSheet("font-weight: bold;")
        db_layout.addWidget(flag_label)
        flag_scroll = QScrollArea()
        flag_scroll.setWidgetResizable(True)
        flag_scroll.setMaximumHeight(140)
        flag_scroll.setFrameShape(QFrame.NoFrame)
        flag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        flag_inner = QWidget()
        flag_grid = QGridLayout(flag_inner)
        self._flag_checks = []
        for i, (val, name, desc) in enumerate(FLAG_DEFINITIONS):
            if val == 0:
                continue
            cb = QCheckBox(f"0x{val:04X} {name}")
            cb.setToolTip(desc)
            self._flag_checks.append((i, cb))
            r, c = (i - 1) // 3, (i - 1) % 3
            flag_grid.addWidget(cb, r, c)
        flag_scroll.setWidget(flag_inner)
        db_layout.addWidget(flag_scroll)
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("목록 검색"))
        self._search_text = QLineEdit()
        self._search_text.setPlaceholderText("지역/스크린네임/플래그 등 텍스트 검색")
        self._search_text.returnPressed.connect(self._on_apply_filter)
        search_row.addWidget(self._search_text)
        db_layout.addLayout(search_row)
        btn_apply = QPushButton("검색")
        btn_apply.clicked.connect(self._on_apply_filter)
        db_layout.addWidget(btn_apply)
        radius_row = QHBoxLayout()
        radius_row.addWidget(QLabel("검색 반경 (km)"))
        self._filter_radius_km = QSpinBox()
        self._filter_radius_km.setRange(MIN_FILTER_RADIUS_KM, MAX_FILTER_RADIUS_KM)
        self._filter_radius_km.setSingleStep(FILTER_RADIUS_STEP_KM)
        self._filter_radius_km.setValue(DEFAULT_FILTER_RADIUS_KM)
        self._filter_radius_km.valueChanged.connect(self._on_filter_radius_changed)
        radius_row.addWidget(self._filter_radius_km)
        radius_row.addStretch()
        db_layout.addLayout(radius_row)

        self._table = QTableWidget()
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            "QTableWidget::item:selected{"
            "background-color:#4a90d9;"
            "color:#ffffff;"
            "}"
            "QTableWidget::item:selected:!active{"
            "background-color:#4a90d9;"
            "color:#ffffff;"
            "}"
        )
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.verticalScrollBar().valueChanged.connect(self._on_table_scroll)
        db_layout.addWidget(self._table)

        btn_use = QPushButton("선택한 행을 기준점으로 설정 (위 기준 좌표/방향에 채움)")
        btn_use.clicked.connect(self._on_set_reference_from_row)
        db_layout.addWidget(btn_use)

        left_layout.addWidget(db_group)

        # 생성 파라미터: 기준점 직접 입력 또는 DB 행 선택으로 채움
        gen_group = QGroupBox("주행 로그 생성")
        gen_layout = QFormLayout(gen_group)
        gen_layout.setSpacing(8)

        ref_row1 = QHBoxLayout()
        ref_row1.addWidget(QLabel("기준 위도"))
        self._ref_lat_spin = QDoubleSpinBox()
        self._ref_lat_spin.setRange(-90, 90)
        self._ref_lat_spin.setDecimals(6)
        self._ref_lat_spin.setSingleStep(0.0001)
        self._ref_lat_spin.setValue(DEFAULT_REF_LAT)
        ref_row1.addWidget(self._ref_lat_spin)
        ref_row1.addWidget(QLabel("기준 경도"))
        self._ref_lon_spin = QDoubleSpinBox()
        self._ref_lon_spin.setRange(-180, 180)
        self._ref_lon_spin.setDecimals(6)
        self._ref_lon_spin.setSingleStep(0.0001)
        self._ref_lon_spin.setValue(DEFAULT_REF_LON)
        ref_row1.addWidget(self._ref_lon_spin)
        gen_layout.addRow("기준 좌표 (DB 없이 직접 입력 가능)", ref_row1)
        ref_row2 = QHBoxLayout()
        ref_row2.addWidget(QLabel("진행 방향 (도, 0=북 90=동)"))
        self._ref_direction_spin = QDoubleSpinBox()
        self._ref_direction_spin.setRange(0, 360)
        self._ref_direction_spin.setDecimals(1)
        self._ref_direction_spin.setValue(0)
        ref_row2.addWidget(self._ref_direction_spin)
        gen_layout.addRow("", ref_row2)
        for w in (self._ref_lat_spin, self._ref_lon_spin, self._ref_direction_spin):
            w.valueChanged.connect(self._on_route_param_changed)

        fav_row = QHBoxLayout()
        fav_row.addWidget(QLabel("즐겨찾기"))
        self._fav_combo = QComboBox()
        self._fav_combo.setMinimumWidth(180)
        self._fav_combo.currentIndexChanged.connect(self._on_favorite_selected)
        fav_row.addWidget(self._fav_combo)
        btn_add_fav = QPushButton("포인트 추가")
        btn_add_fav.clicked.connect(self._on_add_favorite)
        fav_row.addWidget(btn_add_fav)
        btn_del_fav = QPushButton("삭제")
        btn_del_fav.clicked.connect(self._on_remove_favorite)
        fav_row.addWidget(btn_del_fav)
        gen_layout.addRow("포인트 지점", fav_row)

        dist_row = QHBoxLayout()
        dist_row.addWidget(QLabel("시작 거리 (m)"))
        self._start_dist_m = QDoubleSpinBox()
        self._start_dist_m.setRange(10, 100000)
        self._start_dist_m.setSingleStep(100)
        self._start_dist_m.setValue(1000)
        self._start_dist_m.setDecimals(0)
        dist_row.addWidget(self._start_dist_m)
        dist_row.addWidget(QLabel("종료 거리 (m)"))
        self._end_dist_m = QDoubleSpinBox()
        self._end_dist_m.setRange(10, 100000)
        self._end_dist_m.setSingleStep(100)
        self._end_dist_m.setValue(500)
        self._end_dist_m.setDecimals(0)
        dist_row.addWidget(self._end_dist_m)
        gen_layout.addRow("구간 거리", dist_row)
        self._start_dist_m.valueChanged.connect(self._on_route_param_changed)
        self._end_dist_m.valueChanged.connect(self._on_route_param_changed)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("시작 속도 (km/h)"))
        self._start_speed = QSpinBox()
        self._start_speed.setRange(0, 300)
        self._start_speed.setValue(40)
        speed_row.addWidget(self._start_speed)
        speed_row.addWidget(QLabel("종료 속도 (km/h)"))
        self._end_speed = QSpinBox()
        self._end_speed.setRange(0, 300)
        self._end_speed.setValue(120)
        speed_row.addWidget(self._end_speed)
        speed_row.addWidget(QLabel("속도 단계 (km/h)"))
        self._step_speed = QSpinBox()
        self._step_speed.setRange(1, 50)
        self._step_speed.setValue(5)
        speed_row.addWidget(self._step_speed)
        gen_layout.addRow("주행 속도", speed_row)

        self._btn_generate = QPushButton("GPS 로그 파일 생성")
        self._btn_generate.setMinimumHeight(36)
        self._btn_generate.clicked.connect(self._on_generate)
        gen_layout.addRow("", self._btn_generate)

        left_layout.addWidget(gen_group)
        splitter.addWidget(left)

        # 오른쪽: 지도 (1:1 비율)
        if HAS_WEBENGINE:
            self._map_view = QWebEngineView()
            self._map_bridge = MapBridge(self)
            self._map_bridge.route_changed.connect(self._on_map_route_moved)
            self._map_bridge.nearby_hovered.connect(self._on_nearby_db_hovered)
            self._web_channel = QWebChannel(self._map_view.page())
            self._web_channel.registerObject("bridge", self._map_bridge)
            self._map_view.page().setWebChannel(self._web_channel)
            self._map_view.setHtml(_make_map_html(), QUrl("https://example.com"))
            try:
                profile = self._map_view.page().profile()
                profile.setUrlRequestInterceptor(OSMInterceptor())
            except Exception:
                pass
            self._map_view.loadFinished.connect(self._on_map_loaded)
            map_container = MapAspectWidget(self._map_view)
            map_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            map_container.setMinimumWidth(420)
            splitter.addWidget(map_container)
        else:
            placeholder = QLabel("지도 표시를 위해 PyQtWebEngine을 설치하세요:\npip install PyQtWebEngine")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("color: #666; padding: 40px;")
            splitter.addWidget(placeholder)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([680, 840])
        main_layout.addWidget(splitter)

        self._load_favorites_into_combo()
        QTimer.singleShot(100, self._start_default_db_load)

    def _start_default_db_load(self) -> None:
        """db 폴더에서 첫 DB 파일을 찾아 백그라운드로 로드."""
        db_dir = _find_db_dir()
        if db_dir is None:
            self._status.showMessage("db 폴더가 없습니다. DB 파일을 열어 주세요.")
            return
        exts = (".xlsx", ".xls", ".csv", ".tsv", ".txt")
        candidates = []
        try:
            for f in sorted(db_dir.iterdir()):
                if f.is_file() and f.suffix.lower() in exts:
                    candidates.append(f)
        except OSError:
            self._status.showMessage("db 폴더를 읽을 수 없습니다.")
            return
        if not candidates:
            self._status.showMessage("db 폴더에 DB 파일이 없습니다.")
            return
        first = str(candidates[0].resolve())
        self._db_has_more = True
        self._db_loader = DBLoaderThread(first, limit=None, offset=0, parent=self)
        self._db_loader.db_loaded.connect(self._on_db_loaded)
        self._db_loader.finished.connect(self._on_db_loader_finished)
        self._db_loader.start()

    def _on_db_loader_finished(self) -> None:
        """로더 스레드 종료 시 _db_loader 참조만 해제."""
        self._db_loader = None

    def _on_table_scroll(self, value: int) -> None:
        """하단 근처 스크롤 시 DB 추가 로드."""
        sb = self._table.verticalScrollBar()
        if not self._db_has_more or not self._db_path:
            return
        if self._db_loader is not None and self._db_loader.isRunning():
            return
        if sb.maximum() <= 0 or value >= sb.maximum() - 80:
            self._load_more_db()

    def _load_more_db(self) -> None:
        """다음 500행 백그라운드 로드."""
        if not self._db_has_more or not self._db_path or self._db_loader is not None:
            return
        offset = len(self._db_rows)
        self._status.showMessage(f"DB 추가 로딩 중… ({offset}~)")
        self._db_loader = DBLoaderThread(
            self._db_path, limit=CHUNK_SIZE, offset=offset, parent=self
        )
        self._db_loader.db_loaded.connect(self._on_db_loaded)
        self._db_loader.finished.connect(self._on_db_loader_finished)
        self._db_loader.start()

    def _on_db_loaded(self, path: str, rows: list) -> None:
        """백그라운드 DB 로드 완료. 첫 청크면 교체, 추가 청크면 append."""
        loader_limit = self._db_loader._limit if self._db_loader is not None else None
        if self._db_path != path:
            self._db_path = path
            self._db_rows = []
            self._row_coords = []
            self._spatial_index = {}
            self._filtered_rows = []
            self._filtered_indices = []
        if loader_limit is None:
            self._db_has_more = False
        elif len(rows) < CHUNK_SIZE:
            self._db_has_more = False
        if rows:
            start_idx = len(self._db_rows)
            self._db_rows.extend(rows)
            self._index_rows(rows, start_idx)
        self._label_file.setText(Path(path).name)
        if not self._db_rows:
            msg = "파일에서 데이터를 읽지 못했습니다."
            if path.lower().endswith(".xlsx"):
                from gps_log_generator_app.db_parser import HAS_OPENPYXL
                if not HAS_OPENPYXL:
                    msg += "\n\nExcel 로드에는 openpyxl이 필요합니다: pip install openpyxl"
            QMessageBox.warning(self, "로드 실패", msg)
            self._status.showMessage("DB 로드 실패")
            return
        self._apply_filter_internal()
        self._status.showMessage(f"DB 로드: {len(self._db_rows)}행" + ("" if self._db_has_more else " (전체)"))

    def _load_favorites_into_combo(self) -> None:
        """data/favorite.json 목록을 콤보에 채움."""
        self._favorites = load_favorites()
        self._fav_combo.blockSignals(True)
        self._fav_combo.clear()
        self._fav_combo.addItem("— 선택 —", -1)
        for i, item in enumerate(self._favorites):
            self._fav_combo.addItem(item.get("name", ""), i)
        self._fav_combo.blockSignals(False)

    def _on_favorite_selected(self, index: int) -> None:
        if index <= 0:
            return
        idx = self._fav_combo.itemData(index)
        if idx is None or not 0 <= idx < len(self._favorites):
            return
        item = self._favorites[idx]
        self._ref_lat_spin.setValue(float(item.get("lat", 0)))
        self._ref_lon_spin.setValue(float(item.get("lon", 0)))
        self._ref_direction_spin.setValue(float(item.get("direction", 0)))
        self._update_map_from_distances()
        self._status.showMessage(f"포인트 적용: {item.get('name', '')}")

    def _on_add_favorite(self) -> None:
        name, ok = QInputDialog.getText(self, "포인트 추가", "이름:")
        if not ok or not name.strip():
            return
        ref_lat = self._ref_lat_spin.value()
        ref_lon = self._ref_lon_spin.value()
        direction = self._ref_direction_spin.value()
        start_km = self._start_dist_m.value() / 1000.0
        end_km = self._end_dist_m.value() / 1000.0
        start_lat, start_lon, end_lat, end_lon = start_end_from_reference(
            ref_lat, ref_lon, direction, start_km, end_km,
        )
        item = {
            "name": name.strip(),
            "lat": ref_lat,
            "lon": ref_lon,
            "direction": direction,
            "start_lat": start_lat,
            "start_lon": start_lon,
            "end_lat": end_lat,
            "end_lon": end_lon,
        }
        self._favorites.append(item)
        save_favorites(self._favorites)
        self._load_favorites_into_combo()
        self._fav_combo.setCurrentIndex(self._fav_combo.count() - 1)
        self._status.showMessage(f"포인트 추가: {name}")

    def _on_remove_favorite(self) -> None:
        idx = self._fav_combo.currentData()
        if idx is None or idx < 0 or idx >= len(self._favorites):
            QMessageBox.information(self, "알림", "삭제할 포인트를 선택해 주세요.")
            return
        name = self._favorites[idx].get("name", "")
        self._favorites.pop(idx)
        save_favorites(self._favorites)
        self._load_favorites_into_combo()
        self._status.showMessage(f"포인트 삭제: {name}")

    def _get_flag_mask(self) -> int:
        checked = {idx for idx, cb in self._flag_checks if cb.isChecked()}
        return flag_mask_from_indices(checked)

    def _on_open_db(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "DB 파일 선택", str(_find_db_dir() or Path.home()),
            "Excel (*.xlsx);;TSV/CSV (*.tsv *.csv *.txt);;All (*.*)",
        )
        if not path:
            return
        if path.lower().endswith(".xlsx"):
            from gps_log_generator_app.db_parser import HAS_OPENPYXL
            if not HAS_OPENPYXL:
                QMessageBox.warning(self, "로드 실패", "Excel 로드에는 openpyxl이 필요합니다.\npip install openpyxl")
                return
        self._status.showMessage("DB 로딩 중…")
        loader = self._db_loader
        if loader is not None and loader.isRunning():
            loader.terminate()
            loader.wait(2000)
        self._db_path = ""
        self._db_has_more = True
        self._db_loader = DBLoaderThread(path, limit=None, offset=0, parent=self)
        self._db_loader.db_loaded.connect(self._on_db_loaded)
        self._db_loader.finished.connect(self._on_db_loader_finished)
        self._db_loader.start()

    def _on_apply_filter(self):
        if not self._db_rows:
            QMessageBox.information(self, "알림", "먼저 DB 파일을 열어 주세요.")
            return
        self._filter_debounce_timer.stop()
        self._apply_filter_internal()

    @staticmethod
    def _grid_key(lat: float, lon: float) -> tuple[int, int]:
        return (
            int(math.floor((lat + 90.0) / SPATIAL_CELL_DEG)),
            int(math.floor((lon + 180.0) / SPATIAL_CELL_DEG)),
        )

    def _index_rows(self, rows: list[dict], start_idx: int) -> None:
        for offset, row in enumerate(rows):
            lat = get_numeric(row, COL_Y, float("nan"))
            lon = get_numeric(row, COL_X, float("nan"))
            if math.isnan(lat) or math.isnan(lon) or not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                self._row_coords.append(None)
                continue
            self._row_coords.append((lat, lon))
            key = self._grid_key(lat, lon)
            self._spatial_index.setdefault(key, []).append(start_idx + offset)

    @staticmethod
    def _bbox_for_radius(ref_lat: float, ref_lon: float, radius_m: float) -> tuple[float, float, float, float]:
        lat_delta = radius_m / 111320.0
        cos_lat = max(0.0001, math.cos(math.radians(ref_lat)))
        lon_delta = radius_m / (111320.0 * cos_lat)
        min_lat = max(-90.0, ref_lat - lat_delta)
        max_lat = min(90.0, ref_lat + lat_delta)
        min_lon = ref_lon - lon_delta
        max_lon = ref_lon + lon_delta
        if min_lon < -180.0:
            min_lon += 360.0
        if max_lon > 180.0:
            max_lon -= 360.0
        return min_lat, max_lat, min_lon, max_lon

    @staticmethod
    def _lon_in_bbox(lon: float, min_lon: float, max_lon: float) -> bool:
        if min_lon <= max_lon:
            return min_lon <= lon <= max_lon
        return lon >= min_lon or lon <= max_lon

    def _candidate_indices_by_radius(self, ref_lat: float, ref_lon: float, radius_m: float) -> list[int]:
        if not self._row_coords:
            return []
        min_lat, max_lat, min_lon, max_lon = self._bbox_for_radius(ref_lat, ref_lon, radius_m)
        min_lat_key, min_lon_key = self._grid_key(min_lat, min_lon)
        max_lat_key, max_lon_key = self._grid_key(max_lat, max_lon)

        max_lon_bucket = int(math.floor(360.0 / SPATIAL_CELL_DEG)) + 1
        lon_ranges = (
            [(min_lon_key, max_lon_key)]
            if min_lon <= max_lon
            else [(0, max_lon_key), (min_lon_key, max_lon_bucket)]
        )
        candidate_indices = []
        for lat_key in range(min_lat_key, max_lat_key + 1):
            for lon_start, lon_end in lon_ranges:
                for lon_key in range(lon_start, lon_end + 1):
                    candidate_indices.extend(self._spatial_index.get((lat_key, lon_key), []))

        bbox_indices = []
        for idx in candidate_indices:
            coord = self._row_coords[idx] if idx < len(self._row_coords) else None
            if coord is None:
                continue
            lat, lon = coord
            if min_lat <= lat <= max_lat and self._lon_in_bbox(lon, min_lon, max_lon):
                bbox_indices.append(idx)
        return sorted(set(bbox_indices))

    @staticmethod
    def _row_matches_flag(row: dict, flag_mask: int | None) -> bool:
        if not flag_mask:
            return True
        try:
            val = row.get(COL_FLAG, 0)
            val = 0 if val in ("", None) else int(val)
            return (val & flag_mask) == flag_mask
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _row_matches_text(row: dict, query: str) -> bool:
        if not query:
            return True
        q = query.lower()
        for v in row.values():
            if q in str(v).lower():
                return True
        return False

    def _candidate_indices_by_constraints(self, ref_lat: float, ref_lon: float, radius_m: float | None) -> list[int]:
        if radius_m is None:
            return list(range(len(self._db_rows)))
        return self._candidate_indices_by_radius(ref_lat, ref_lon, radius_m)

    @staticmethod
    def _search_radius_steps(base_radius_m: float) -> list[float | None]:
        r1 = max(1000.0, base_radius_m)
        r2 = min(120000.0, r1 * 2.0)
        r3 = min(240000.0, r1 * 4.0)
        r4 = 300000.0
        radii = []
        for r in (r1, r2, r3, r4):
            if all(abs(r - x) > 1.0 for x in radii if x is not None):
                radii.append(r)
        radii.append(None)
        return radii

    def _schedule_filter_apply(self):
        if not self._db_rows:
            return
        self._filter_debounce_timer.start(FILTER_DEBOUNCE_MS)

    def _on_filter_radius_changed(self, _value: int):
        self._schedule_filter_apply()

    def _current_filter_radius_m(self) -> float:
        if hasattr(self, "_filter_radius_km"):
            return float(self._filter_radius_km.value()) * 1000.0
        return float(DEFAULT_FILTER_RADIUS_KM * 1000.0)

    def _apply_filter_internal(self):
        mask = self._get_flag_mask()
        ref_lat = self._ref_lat_spin.value()
        ref_lon = self._ref_lon_spin.value()
        base_radius_m = self._current_filter_radius_m()
        query = self._search_text.text().strip() if hasattr(self, "_search_text") else ""
        nearby_indices = []
        used_radius = base_radius_m

        for radius_m in self._search_radius_steps(base_radius_m):
            matched = []
            for idx in self._candidate_indices_by_constraints(ref_lat, ref_lon, radius_m):
                row = self._db_rows[idx]
                if not self._row_matches_flag(row, mask):
                    continue
                if not self._row_matches_text(row, query):
                    continue
                if radius_m is not None:
                    coord = self._row_coords[idx] if idx < len(self._row_coords) else None
                    if coord is None:
                        continue
                    lat, lon = coord
                    if self._distance_m(ref_lat, ref_lon, lat, lon) > radius_m:
                        continue
                matched.append(idx)
            nearby_indices = matched
            used_radius = radius_m
            if len(nearby_indices) > SEARCH_EXPAND_THRESHOLD or radius_m is None:
                break

        self._filtered_indices = nearby_indices
        self._filtered_rows = [self._db_rows[i] for i in nearby_indices]
        self._fill_table()
        self._update_nearby_db_markers()
        radius_label = "전체 범위" if used_radius is None else f"{int(used_radius)}m"
        query_label = f", 목록 검색: '{query}'" if query else ""
        if self._filtered_rows:
            self._status.showMessage(
                f"검색 결과: {len(self._filtered_rows)}행 (기준점 반경 {radius_label}{query_label})"
            )
        else:
            self._status.showMessage(
                f"검색 결과: 0행 (기준점 반경 {radius_label}{query_label})"
            )

    def _fill_table(self):
        if not self._filtered_indices:
            self._table.setRowCount(0)
            self._table.setColumnCount(0)
            return
        cols = TABLE_DISPLAY_COLUMNS
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels([label for _key, label in cols])
        self._table.setRowCount(len(self._filtered_indices))
        for r in range(len(self._filtered_indices)):
            db_idx = self._filtered_indices[r]
            row = self._db_rows[db_idx]
            for c, (key, _label) in enumerate(cols):
                self._table.setItem(r, c, QTableWidgetItem(str(row.get(key, ""))))

    def _on_selection_changed(self):
        # DB 목록은 검색 결과 확인용으로 동작하고, 기준점 적용은 버튼 클릭 시에만 수행한다.
        return

    def _on_nearby_db_hovered(self, table_row: int):
        if table_row < 0 or table_row >= len(self._filtered_indices):
            return
        self._table.blockSignals(True)
        try:
            self._table.selectRow(table_row)
            self._table.scrollToItem(
                self._table.item(table_row, 0),
                QAbstractItemView.PositionAtCenter,
            )
        finally:
            self._table.blockSignals(False)

    def _apply_distance_limits_for_reference(self) -> bool:
        start_m = self._start_dist_m.value()
        end_m = self._end_dist_m.value()
        clamped_start_m = min(start_m, MAX_START_DIST_M)
        clamped_end_m = min(end_m, MAX_END_DIST_M)
        if clamped_start_m == start_m and clamped_end_m == end_m:
            return False

        ref_lat = self._ref_lat_spin.value()
        ref_lon = self._ref_lon_spin.value()
        cur_dir = self._ref_direction_spin.value()
        cur_start_lat, cur_start_lon, _end_lat, _end_lon = start_end_from_reference(
            ref_lat, ref_lon, cur_dir, start_m / 1000.0, end_m / 1000.0,
        )
        direction = self._bearing_deg(cur_start_lat, cur_start_lon, ref_lat, ref_lon)

        self._is_updating_from_map = True
        try:
            self._ref_direction_spin.setValue(direction)
            self._start_dist_m.setValue(clamped_start_m)
            self._end_dist_m.setValue(clamped_end_m)
        finally:
            self._is_updating_from_map = False
        self._custom_route_override = None
        self._update_map_from_distances()
        return True

    def _on_set_reference_from_row(self, skip_confirm=False):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._filtered_indices):
            if not skip_confirm:
                QMessageBox.information(self, "알림", "테이블에서 행을 선택해 주세요.")
            return
        rec = self._db_rows[self._filtered_indices[row]]
        self._ref_lat_spin.setValue(get_numeric(rec, COL_Y))
        self._ref_lon_spin.setValue(get_numeric(rec, COL_X))
        self._ref_direction_spin.setValue(get_numeric(rec, COL_DIRECTION, 0))
        self._ref_speed = get_numeric(rec, COL_SPEED, 50)
        self._start_speed.setValue(int(self._ref_speed) if self._ref_speed == int(self._ref_speed) else max(0, int(self._ref_speed)))
        self._end_speed.setValue(max(self._start_speed.value(), int(self._ref_speed) + 40))
        self._custom_route_override = None
        limited = self._apply_distance_limits_for_reference()
        self._update_map_from_distances()
        if limited:
            self._status.showMessage(
                "기준점 설정됨 – 거리 제한 적용(시작 3km, 종료 1km), 기준점 기준으로 경로를 조정했습니다."
            )
        else:
            self._status.showMessage("기준점 설정됨 – 이 지점을 지나는 로그가 생성됩니다.")

    def _on_map_loaded(self):
        self._update_map_from_distances()
        self._update_nearby_db_markers()

    def _on_route_param_changed(self):
        if self._is_updating_from_map:
            return
        self._custom_route_override = None
        self._update_map_from_distances()
        self._schedule_filter_apply()

    def _update_map_from_distances(self):
        if self._is_updating_from_map:
            return
        if not HAS_WEBENGINE or not hasattr(self, "_map_view"):
            return
        if self._custom_route_override is not None:
            ref_lat, ref_lon, start_lat, start_lon, end_lat, end_lon = self._custom_route_override
        else:
            ref_lat = self._ref_lat_spin.value()
            ref_lon = self._ref_lon_spin.value()
            direction = self._ref_direction_spin.value()
            start_km = self._start_dist_m.value() / 1000.0
            end_km = self._end_dist_m.value() / 1000.0
            start_lat, start_lon, end_lat, end_lon = start_end_from_reference(
                ref_lat, ref_lon, direction, start_km, end_km,
            )
        js = f"if (typeof updateRoute === 'function') updateRoute({ref_lat}, {ref_lon}, {start_lat}, {start_lon}, {end_lat}, {end_lon});"
        self._map_view.page().runJavaScript(js)

    @staticmethod
    def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return radius * c

    @staticmethod
    def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dlambda = math.radians(lon2 - lon1)
        y = math.sin(dlambda) * math.cos(phi2)
        x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
        return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0

    def _on_map_route_moved(
        self,
        ref_lat: float,
        ref_lon: float,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
    ):
        start_m = self._distance_m(ref_lat, ref_lon, start_lat, start_lon)
        end_m = self._distance_m(ref_lat, ref_lon, end_lat, end_lon)
        if self._distance_m(start_lat, start_lon, end_lat, end_lon) >= 1.0:
            direction = self._bearing_deg(start_lat, start_lon, end_lat, end_lon)
        elif end_m >= 1.0:
            direction = self._bearing_deg(ref_lat, ref_lon, end_lat, end_lon)
        elif start_m >= 1.0:
            direction = self._bearing_deg(start_lat, start_lon, ref_lat, ref_lon)
        else:
            direction = self._ref_direction_spin.value()

        self._is_updating_from_map = True
        try:
            self._ref_lat_spin.setValue(ref_lat)
            self._ref_lon_spin.setValue(ref_lon)
            self._ref_direction_spin.setValue(direction)
            self._start_dist_m.setValue(start_m)
            self._end_dist_m.setValue(end_m)
        finally:
            self._is_updating_from_map = False
        # 지도에서 드래그한 1/2/3번 좌표를 그대로 유지한다.
        self._custom_route_override = (ref_lat, ref_lon, start_lat, start_lon, end_lat, end_lon)
        self._schedule_filter_apply()
        self._status.showMessage("지도에서 시작/기준/종료 지점을 이동해 경로를 조정했습니다.")

    def _update_nearby_db_markers(self):
        if not HAS_WEBENGINE or not hasattr(self, "_map_view"):
            return

        radius_m = self._current_filter_radius_m()
        nearby_points = []
        for table_row, row in enumerate(self._filtered_rows):
            lat = get_numeric(row, COL_Y, float("nan"))
            lon = get_numeric(row, COL_X, float("nan"))
            if math.isnan(lat) or math.isnan(lon):
                continue
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                continue
            nearby_points.append({"lat": lat, "lon": lon, "row": table_row})

        points_json = json.dumps(nearby_points, ensure_ascii=False)
        js = (
            "if (typeof setNearbyPoints === 'function') "
            f"setNearbyPoints({points_json});"
        )
        self._map_view.page().runJavaScript(js)
        self._status.showMessage(
            f"주변 DB 핀 표시: {len(nearby_points)}개 "
            f"(반경 {int(radius_m)}m)"
        )

    def _on_generate(self):
        ref_lat = self._ref_lat_spin.value()
        ref_lon = self._ref_lon_spin.value()
        direction = self._ref_direction_spin.value()
        limited = False
        if self._custom_route_override is not None:
            (
                ref_lat,
                ref_lon,
                start_lat,
                start_lon,
                end_lat,
                end_lon,
            ) = self._custom_route_override
            start_m = self._distance_m(start_lat, start_lon, ref_lat, ref_lon)
            end_m = self._distance_m(ref_lat, ref_lon, end_lat, end_lon)
            clamped_start_m = min(start_m, MAX_START_DIST_M)
            clamped_end_m = min(end_m, MAX_END_DIST_M)
            if clamped_start_m != start_m or clamped_end_m != end_m:
                limited = True
                direction = self._bearing_deg(start_lat, start_lon, ref_lat, ref_lon)
                start_km = clamped_start_m / 1000.0
                end_km = clamped_end_m / 1000.0
                start_lat, start_lon, end_lat, end_lon = start_end_from_reference(
                    ref_lat, ref_lon, direction, start_km, end_km,
                )
                total_km = start_km + end_km
            else:
                direction = self._bearing_deg(start_lat, start_lon, end_lat, end_lon)
                total_km = (
                    self._distance_m(start_lat, start_lon, ref_lat, ref_lon)
                    + self._distance_m(ref_lat, ref_lon, end_lat, end_lon)
                ) / 1000.0
        else:
            start_dist_m = self._start_dist_m.value()
            end_dist_m = self._end_dist_m.value()
            clamped_start_m = min(start_dist_m, MAX_START_DIST_M)
            clamped_end_m = min(end_dist_m, MAX_END_DIST_M)
            if clamped_start_m != start_dist_m or clamped_end_m != end_dist_m:
                limited = True
                raw_start_lat, raw_start_lon, _raw_end_lat, _raw_end_lon = start_end_from_reference(
                    ref_lat, ref_lon, direction, start_dist_m / 1000.0, end_dist_m / 1000.0,
                )
                direction = self._bearing_deg(raw_start_lat, raw_start_lon, ref_lat, ref_lon)
                start_dist_km = clamped_start_m / 1000.0
                end_dist_km = clamped_end_m / 1000.0
            else:
                start_dist_km = start_dist_m / 1000.0
                end_dist_km = end_dist_m / 1000.0
            start_lat, start_lon, end_lat, end_lon = start_end_from_reference(
                ref_lat, ref_lon, direction, start_dist_km, end_dist_km,
            )
            total_km = start_dist_km + end_dist_km
        iterations = max(MIN_POINTS, min(MAX_POINTS, int(total_km * POINTS_PER_KM)))
        try:
            path = gps.generate(
                start_lat, start_lon, end_lat, end_lon,
                start_speed=float(self._start_speed.value()),
                end_speed=float(self._end_speed.value()),
                step_speed=float(self._step_speed.value()),
                heading=direction,
                iterations=iterations,
            )
        except Exception as e:
            QMessageBox.critical(self, "오류", f"생성 중 오류: {e}")
            return
        notice = ""
        if limited:
            notice = (
                "\n\n시작거리와 끝거리가 멀어 기준점 쪽으로 옮겼습니다."
                " (시작 3km, 종료 1km 제한 적용)"
            )
        QMessageBox.information(self, "완료", f"GPS 로그가 생성되었습니다.{notice}\n\n저장: {path}")
        self._status.showMessage(f"로그 저장: {path}")


def main():
    app = QApplication([])
    app.setStyle("Fusion")
    font = app.font()
    if font.pointSize() > 0:
        font.setPointSize(max(7, font.pointSize() - 2))
    else:
        font.setPixelSize(max(10, (font.pixelSize() or 13) - 2))
    app.setFont(font)
    w = GpsLogGeneratorWindow()
    w.show()
    app.exec_()


if __name__ == "__main__":
    main()
