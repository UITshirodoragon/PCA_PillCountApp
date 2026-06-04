# SRS - Pill Counter v0.1.1 UI/UX Fix & Package Refactor

**Tên dự án:** Pill Counter  
**Phiên bản SRS:** v0.1.1  
**Tên bản cập nhật:** UI/UX Correction, In-App Overlay Dialogs, PharmCam-like Counting, Cloudflare-first Share  
**Baseline:** v0.1.0 Big Refactor  
**Gói mã nguồn cập nhật:** `pill_counter_v0.1.1.zip`  
**Trạng thái:** Bản triển khai đóng gói kèm SRS  

---

## 1. Mục tiêu bản v0.1.1

Phiên bản v0.1.1 là bản sửa lỗi và tinh chỉnh sau SRS v0.1.0. Trọng tâm không phải thay đổi mô hình PANet hoặc nghiệp vụ inference, mà là sửa các vấn đề UX/UI cụ thể khi triển khai trên màn hình cảm ứng 1024×600.

Mục tiêu chính:

- Biến các hộp thoại native/dialog thành overlay nằm trong app để bàn phím ảo nội bộ có thể nhập được.
- Chỉ hiển thị trạng thái Camera/Model/Tunnel ở Menu Screen.
- Đồng bộ nền text/label/input/card để không còn tình trạng text nền trắng nằm lệch trên widget nền xanh.
- Cải tiến Counting Screen theo hướng giống giao diện chụp ảnh điện thoại nằm ngang, học từ PharmCam.
- Dùng hài hòa đủ 5 màu medical palette, không chỉ dùng màu đỏ cho cảnh báo.
- Sửa bàn phím nội bộ: có viền ngoài, viền từng nút, vùng preview nội dung đang gõ, nút Hide.
- Phóng to các button ở Menu Screen, tên app là “Pill Counter”, version chỉ hiển thị nhỏ.
- Quick Menu dạng overlay/drawer có animation, không làm thay đổi bố cục màn hình hiện tại.
- Cloudflare Quick Tunnel là hướng chia sẻ mặc định để người ngoài mạng có thể quét QR và mở report.
- Tiếp tục bỏ Nucleo/HX711/serial scale khỏi runtime.

---

## 2. Phạm vi thay đổi

### 2.1. In scope

- Refactor `MainWindow` để có Menu Screen, App Shell header tối giản, animated side drawer, keyboard overlay và app overlay.
- Thêm `MenuPage` mới.
- Thêm `AppOverlay` mới thay cho `QMessageBox` và `DrugEditDialog` trong workflow chính.
- Viết lại `CountPage` theo layout camera-app landscape.
- Sửa `VirtualKeyboardWidget` và `KeyboardController`.
- Sửa `SettingsPage` bỏ serial/scale, thêm Cloudflare config.
- Sửa `MainPresenter` bỏ serial worker, dùng overlay dialog, quản lý share/tunnel.
- Thêm `TunnelWorker` dùng `cloudflared tunnel --url http://127.0.0.1:<port> --no-autoupdate`.
- Sửa Flask share worker để hỗ trợ token trong URL report.
- Cập nhật QSS medical palette.
- Cập nhật README/CHANGELOG/config/requirements.

### 2.2. Out of scope

- Không train lại model.
- Không triển khai cloud database hoặc web dashboard.
- Không triển khai PMS integration.
- Không triển khai barcode/Rx workflow đầy đủ.
- Không đảm bảo Cloudflare Tunnel hoạt động nếu thiết bị chưa cài `cloudflared` hoặc mất Internet.
- Không kiểm thử thực tế trên Raspberry Pi 5 trong môi trường đóng gói này.

---

## 3. Yêu cầu phần cứng/phần mềm

| Nhóm | Yêu cầu |
|---|---|
| Board chạy app | Raspberry Pi 5 4GB RAM |
| Camera | Logitech C930C hoặc UVC camera tương thích OpenCV/V4L2 |
| Màn hình | Waveshare 7 inch HDMI touch, 1024×600 landscape |
| OS | Raspberry Pi OS / Linux desktop |
| Python | 3.10 hoặc 3.11 khuyến nghị |
| GUI | PyQt6 |
| AI runtime | PyTorch CPU |
| Share local | Flask/Werkzeug |
| Share public | `cloudflared` external binary |
| Database | SQLite local |

---

## 4. Medical UI palette

| Token | Hex | Vai trò trong v0.1.1 |
|---|---|---|
| Warm Background | `#fffeef` | Nền tổng thể, input, vùng camera text, QR text |
| Primary Blue | `#4b7a9f` | Nút chính, title, header, drawer, trạng thái chính |
| Secondary Blue | `#8ebcca` | Border, secondary button, pressed state, accent |
| Mint Panel | `#ccede6` | Card/panel/menu status/keyboard nền |
| Danger Red | `#cc0000` | Shutter/Capture, delete, cảnh báo nghiêm trọng |

Quy tắc màu:

- Không dùng đỏ làm màu nhấn chính; đỏ chỉ dùng cho hành động nguy hiểm hoặc trạng thái lỗi.
- Input và label trong card phải có background/border đồng bộ, không để text trắng rời rạc trên nền xanh.
- Mọi cảnh báo phải có text đi kèm, không chỉ dựa vào màu.

---

## 5. Kiến trúc UI v0.1.1

```text
MainWindow
├── MenuPage
│   ├── Title: Pill Counter
│   ├── Version nhỏ: v0.1.1
│   ├── Status: Camera / Model / Tunnel
│   └── 6 nút lớn: Count, Inventory, Reports, Logs, Settings, Diagnostics
├── Header tối giản cho các screen không phải Menu
│   ├── Menu icon ☰
│   └── Screen title
├── CountPage
│   ├── Count card
│   ├── Camera canvas
│   ├── Session card
│   └── Bottom action row
├── InventoryPage
├── SettingsPage
├── Animated Side Drawer
├── AppOverlay
└── VirtualKeyboardWidget
```

---

## 6. Yêu cầu chức năng cập nhật

### 6.1. Menu Screen

| Mã | Yêu cầu | Ưu tiên | Tiêu chí nghiệm thu |
|---|---|---|---|
| FR-101 | Hệ thống phải mở trực tiếp vào Menu Screen, không dùng Start Screen cũ. | Must | Chạy `python app.py` vào Menu toàn màn hình. |
| FR-102 | Menu phải có tên app “Pill Counter”. | Must | Không còn title cũ/patch v3. |
| FR-103 | Version phải hiển thị nhỏ, không chiếm vùng thao tác. | Must | `v0.1.1` nằm dưới title hoặc trong label nhỏ. |
| FR-104 | Menu phải có nút lớn cho Count, Inventory, Reports, Logs, Settings, Diagnostics. | Must | Mỗi nút đủ lớn để bấm bằng cảm ứng. |
| FR-105 | Chỉ Menu mới hiển thị Camera/Model/Tunnel status. | Must | Các screen khác không còn status bar camera/model/tunnel. |

### 6.2. App overlay thay native dialogs

| Mã | Yêu cầu | Ưu tiên | Tiêu chí nghiệm thu |
|---|---|---|---|
| FR-120 | Các xác nhận Delete/Clear/Archive phải dùng overlay trong app thay vì QMessageBox. | Must | Overlay nằm đè trên app; không mở cửa sổ native. |
| FR-121 | Add/Edit Drug phải dùng overlay form trong app thay vì QDialog. | Must | Bấm Add/Edit mở form overlay. |
| FR-122 | Virtual keyboard phải nhập được vào field trong overlay. | Must | Focus vào field overlay làm keyboard hiển thị và nhập đúng. |
| FR-123 | Overlay không được làm thay đổi layout screen bên dưới. | Must | Đóng overlay, layout ban đầu giữ nguyên. |

### 6.3. Virtual keyboard

| Mã | Yêu cầu | Ưu tiên | Tiêu chí nghiệm thu |
|---|---|---|---|
| FR-140 | Keyboard phải có viền ngoài rõ. | Must | Khung keyboard có border xanh. |
| FR-141 | Từng nút trên keyboard phải có viền. | Must | Nút chữ/số có border riêng. |
| FR-142 | Keyboard phải có preview nội dung đang gõ. | Must | Preview cập nhật sau mỗi ký tự/backspace. |
| FR-143 | Keyboard phải có nút Hide. | Must | Bấm Hide ẩn keyboard. |
| FR-144 | Keyboard phải tự hiện khi focus vào input field. | Must | Không cần bật native Qt virtual keyboard. |
| FR-145 | Keyboard phải hỗ trợ QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox. | Should | Có thể nhập text và số trong Settings/Overlay. |

### 6.4. Counting Screen kiểu camera app landscape

| Mã | Yêu cầu | Ưu tiên | Tiêu chí nghiệm thu |
|---|---|---|---|
| FR-160 | Counting Screen phải ưu tiên camera canvas lớn ở giữa. | Must | Camera chiếm vùng lớn nhất. |
| FR-161 | Count value phải hiển thị rất lớn. | Must | Nhìn rõ trên 7 inch 1024×600. |
| FR-162 | Layout phải có cảm giác giống app chụp ảnh ngang: canvas, capture, retake, live/stop. | Must | Người dùng thao tác capture/retake ở cạnh dưới camera. |
| FR-163 | Screen phải có `+ Batch`, `− Batch`, `Undo`, `Reset`, `Complete`. | Should | Có thể cộng/trừ count hiện tại vào total session. |
| FR-164 | Session card phải chứa các input tối thiểu: User, Drug, Batch, Notes. | Must | Không còn tab dày đặc như v0.0.4. |
| FR-165 | Không còn Scale tab/Tare/Calibrate/Reset scale. | Must | UI không còn phần cân/Nucleo. |
| FR-166 | Complete lưu effective count: total nếu có batch, nếu không thì current count. | Should | Batch workflow lưu đúng tổng. |

### 6.5. Animated side drawer

| Mã | Yêu cầu | Ưu tiên | Tiêu chí nghiệm thu |
|---|---|---|---|
| FR-180 | Bấm nút Menu ở screen con phải mở quick drawer overlay. | Must | Drawer trượt vào từ cạnh trái. |
| FR-181 | Drawer không được đẩy/reflow layout screen hiện tại. | Must | Camera/Count layout không bị co lại. |
| FR-182 | Drawer phải có animation mở/đóng. | Should | Có QPropertyAnimation khi show/hide. |
| FR-183 | Drawer phải có đường tắt đến Menu, Count, Inventory, Reports, Settings, Diagnostics và Keyboard. | Must | Có thể chuyển screen nhanh. |

### 6.6. Cloudflare Quick Tunnel mặc định

| Mã | Yêu cầu | Ưu tiên | Tiêu chí nghiệm thu |
|---|---|---|---|
| FR-200 | App phải có cấu hình Cloudflare Quick Tunnel mặc định bật. | Must | `config.json` có `cloudflare.enabled = true`. |
| FR-201 | App phải tự chạy local share server trước khi chạy tunnel. | Must | Local server start ở port cấu hình. |
| FR-202 | App phải quản lý process `cloudflared` nếu có. | Should | `TunnelWorker` start/stop process. |
| FR-203 | App phải parse public `trycloudflare.com` URL từ output. | Should | Menu status hiển thị `Tunnel: Online`. |
| FR-204 | QR report phải ưu tiên public URL khi tunnel online. | Must | Link QR dùng `https://*.trycloudflare.com/...`. |
| FR-205 | Nếu tunnel lỗi/chưa cài, app vẫn phải đếm và lưu local bình thường. | Must | Không crash khi thiếu `cloudflared`. |
| FR-206 | Report URL phải có token khi token_required bật. | Must | Link có `?token=...`. |
| FR-207 | Public index toàn bộ reports không được mở khi token_required bật. | Must | Route `/` chỉ báo cần direct token. |

---

## 7. Yêu cầu phi chức năng

| Mã | Nhóm | Yêu cầu |
|---|---|---|
| NFR-001 | Usability | Mọi nút chính phải đủ lớn cho touch trên 7 inch. |
| NFR-002 | Usability | Menu phải rất đơn giản, không hiển thị nhiều thông tin ngoài status cần thiết. |
| NFR-003 | Usability | Counting Screen không dùng tab nhiều tầng trong workflow đếm chính. |
| NFR-004 | Usability | Dialog/overlay/keyboard phải hoạt động trong cùng cửa sổ app. |
| NFR-005 | Visual consistency | Label, input, card phải thống nhất background/border theo medical palette. |
| NFR-006 | Reliability | Thiếu `cloudflared` không được làm app lỗi. |
| NFR-007 | Security | Public report link phải dùng token nếu đi qua tunnel. |
| NFR-008 | Privacy | Ảnh/report mặc định vẫn lưu local; Cloudflare chỉ phục vụ file khi người dùng bật share. |
| NFR-009 | Maintainability | Không còn import runtime tới SerialWorker/SerialService. |
| NFR-010 | Performance | Drawer/overlay/keyboard không được làm restart camera/inference. |

---

## 8. Cấu hình v0.1.1

```json
{
  "camera": {
    "device_index": 0,
    "width": 640,
    "height": 480,
    "fps": 30,
    "profile": "balanced"
  },
  "model": {
    "model_path": "./Networks/weights/model_best.pth",
    "model_arch": "PANet",
    "threshold": 0.4,
    "nms_ksize": 5,
    "min_peak": 0.25,
    "max_peaks": 500,
    "realtime_fps": 6,
    "smoothing_alpha": 0.15
  },
  "serial": {
    "enabled": false,
    "stream_weight": false
  },
  "share": {
    "enable_qr_share": true,
    "port": 5000,
    "bind_all": true,
    "token_required": true
  },
  "cloudflare": {
    "enabled": true,
    "cloudflared_path": "cloudflared",
    "auto_start": true
  }
}
```

---

## 9. Tiêu chí nghiệm thu tổng thể

| Mã | Tiêu chí |
|---|---|
| AC-001 | Chạy app vào Menu Screen, không vào Start Screen. |
| AC-002 | Menu có 6 button lớn và version nhỏ. |
| AC-003 | Status Camera/Model/Tunnel chỉ xuất hiện ở Menu. |
| AC-004 | Count Screen giống camera landscape: camera canvas lớn, count lớn, capture/retake/complete rõ. |
| AC-005 | Add/Edit Drug dùng overlay trong app và keyboard nhập được. |
| AC-006 | Delete/Clear/Archive dùng overlay trong app, không dùng native QMessageBox. |
| AC-007 | Keyboard có border ngoài, key border, preview text và Hide. |
| AC-008 | Drawer mở/đóng bằng animation, không làm co layout Count Screen. |
| AC-009 | Không còn serial worker/service trong runtime. |
| AC-010 | Settings không còn cấu hình serial/scale/Tare/Calibrate. |
| AC-011 | QR report dùng Cloudflare public URL khi tunnel online. |
| AC-012 | Nếu cloudflared không cài, app báo lỗi ở log/status nhưng vẫn count/save/report local. |
| AC-013 | `python3 -m compileall app app.py` không lỗi cú pháp. |

---

## 10. File thay đổi chính trong gói v0.1.1

| File | Thay đổi |
|---|---|
| `app.py` | Bỏ StartScreen; mở trực tiếp MainWindow/Menu. |
| `app/core/constants.py` | Cập nhật version `v0.1.1`, palette và default resolution. |
| `app/core/config.py` | Thêm Cloudflare config, tắt serial runtime, tăng camera default. |
| `app/ui/main_window.py` | App Shell, Menu, header tối giản, animated drawer, overlay, keyboard overlay. |
| `app/ui/pages/menu_page.py` | Màn hình Menu mới. |
| `app/ui/pages/count_page.py` | Count Screen mới dạng camera app landscape. |
| `app/ui/pages/settings_page.py` | Bỏ serial/scale, thêm Cloudflare/share/camera/model. |
| `app/ui/widgets/app_overlay.py` | Overlay nội bộ thay dialog native. |
| `app/ui/widgets/virtual_keyboard.py` | Keyboard preview, border, auto-show, spinbox support. |
| `app/workers/flask_worker.py` | Token-required report route, path traversal safe check. |
| `app/workers/tunnel_worker.py` | Cloudflare Quick Tunnel process worker. |
| `app/presenters/main_presenter.py` | Bỏ serial worker, dùng overlay, Cloudflare/tunnel QR, status ở Menu. |
| `resources/styles/app.qss` | Medical palette UI đồng bộ. |
| `README.md`, `CHANGELOG.md` | Cập nhật hướng dẫn và thay đổi. |

---

## 11. Rủi ro còn lại

| Rủi ro | Ảnh hưởng | Cách xử lý tiếp theo |
|---|---|---|
| Chưa test thực tế trên Raspberry Pi 5 | Có thể còn lỗi camera/backend/touch | Test trực tiếp trên Pi 5 + C930C. |
| Cloudflare Quick Tunnel phụ thuộc binary ngoài | Nếu chưa cài thì không có public URL | Thêm script cài đặt cloudflared trong bản sau. |
| PANet có thể chậm ở 640×480 trên CPU | Count delay | Benchmark, fallback 320×240 hoặc 512×384 nếu cần. |
| Overlay contour vẫn phụ thuộc heatmap hiện tại | Chưa phải outline instance-level như PharmCam thật | Bản sau cải tiến postprocess/segmentation overlay. |
| Batch calculator chưa lưu chi tiết từng thumbnail entry vào schema riêng | Audit batch còn hạn chế | Bản sau thêm bảng `batch_entries`. |

---

## 12. Definition of Done v0.1.1

v0.1.1 được xem là hoàn thành ở mức package hiện tại khi:

- Source code compile không lỗi cú pháp.
- App không còn phụ thuộc serial/Nucleo/HX711 runtime.
- UI đã chuyển sang Menu + Count camera landscape.
- Dialog chính đã thành overlay trong app.
- Keyboard overlay đã sửa chiều cao, preview và border.
- Cloudflare Tunnel worker và config mặc định đã được thêm.
- README, CHANGELOG và SRS đã được cập nhật.
- Gói zip release không chứa `__pycache__`, WAL/SHM/log/report runtime thừa.
