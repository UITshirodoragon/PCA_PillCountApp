# SRS - Pill Counter v0.1.2 Count Screen & Virtual Keyboard UI Fix

**Tên dự án:** Pill Counter  
**Phiên bản SRS:** v0.1.2  
**Tên bản cập nhật:** Count Screen + Virtual Keyboard UX Repair  
**Gói mã nguồn cập nhật:** `pill_counter_v0_1_2.zip`  
**Baseline:** v0.1.1  
**Mục tiêu chính:** sửa lỗi bàn phím ảo, giảm tải Count Screen, và đưa giao diện đếm tiến gần hơn phong cách PharmCam/VIVID nhưng theo layout ngang 1024×600.

---

## 1. Bối cảnh lỗi cần xử lý

Phiên bản v0.1.1 đã chuyển nhiều hộp thoại native sang in-app overlay và đã tạo Count Screen kiểu camera app. Tuy nhiên khi kiểm thử UI vẫn phát sinh các lỗi quan trọng:

- Bàn phím ảo có chiều cao quá thấp, phải scroll mới thấy đủ phím.
- Khi nhập thuốc mới trong overlay nội bộ, focus vào ô text chưa làm keyboard hiện ổn định.
- Count Screen vẫn bị nặng vì phần Session chiếm diện tích cố định quá lớn.
- Giao diện cần dùng bộ màu medical palette hài hòa hơn, đặc biệt cần có điểm nhấn đỏ `#cc0000`.
- Các chức năng phụ của Count Screen nên trở thành popup/widget overlay hiện khi cần, không chiếm layout chính.

---

## 2. Mục tiêu phiên bản v0.1.2

1. Sửa keyboard để **hiện đầy đủ 5 hàng phím** trong một overlay cố định, không cần scroll.
2. Keyboard phải có **viền ngoài rõ**, **viền từng phím**, **preview nội dung đang gõ**, và nút **Hide**.
3. Keyboard phải tự hiện khi focus vào input trong các overlay nội bộ, đặc biệt form thêm/sửa thuốc.
4. Refactor Count Screen theo hướng **landscape camera counter**:
   - Camera canvas là vùng lớn nhất.
   - Count value cực lớn và dễ đọc.
   - Session form ẩn mặc định, mở thành floating panel khi cần.
   - Các nút thao tác giống camera/control bar: `−`, `CAPTURE`, `+`, `Session`, `Complete`.
5. Dùng đủ 5 màu palette:
   - `#fffeef` nền ấm.
   - `#4b7a9f` màu chính.
   - `#8ebcca` màu phụ.
   - `#ccede6` panel nhẹ.
   - `#cc0000` accent/cảnh báo/shutter/focus.
6. Giữ lõi inference, database, report và Cloudflare tunnel như v0.1.1.

---

## 3. Phạm vi thay đổi

### 3.1. In scope

- `VirtualKeyboardWidget`.
- `KeyboardController`.
- `AppOverlay` focus behavior.
- `CountPage` layout.
- QSS/style medical palette.
- Version, README, changelog, package folder name.
- Compile-level sanity check.

### 3.2. Out of scope

- Training model mới.
- Thay đổi kiến trúc PANet.
- Tích hợp barcode/PMS/cloud database thật.
- Kiểm thử phần cứng thật trên Raspberry Pi 5/C930C trong môi trường sandbox.

---

## 4. Yêu cầu chức năng cập nhật

| Mã | Yêu cầu | Ưu tiên | Tiêu chí nghiệm thu |
|---|---|---|---|
| FR-012-001 | Keyboard phải hiển thị đủ toàn bộ phím khi bật. | Must | Không còn cần scroll trong keyboard ở 1024×600. |
| FR-012-002 | Keyboard phải có preview text đang nhập. | Must | Khi gõ, preview cập nhật theo target hiện tại. |
| FR-012-003 | Keyboard phải có nút Hide. | Must | Chạm Hide làm keyboard biến mất. |
| FR-012-004 | Keyboard phải tự hiện khi focus vào QLineEdit/QTextEdit/QSpinBox trong app overlay. | Must | Form thêm thuốc tự mở keyboard khi chạm ô nhập. |
| FR-012-005 | Keyboard phải có border ngoài và border từng phím. | Must | Các phím tách rõ trên màn hình cảm ứng. |
| FR-012-006 | Count Screen phải ẩn Session form mặc định. | Must | Khi vào Count, không có panel Session cố định bên phải. |
| FR-012-007 | Session form phải mở dưới dạng floating panel overlay. | Must | Chạm `Session` hoặc `Verify` mở panel, không làm layout camera/count bị co lại. |
| FR-012-008 | Count Screen phải có camera canvas lớn nhất. | Must | Preview camera chiếm phần trung tâm/rộng nhất của screen. |
| FR-012-009 | Count Screen phải có nút `CAPTURE` dạng shutter với accent đỏ. | Must | Nút capture nổi bật bằng `#cc0000`. |
| FR-012-010 | Count Screen phải có batch controls `−` và `+` dạng nút lớn. | Should | Người dùng cộng/trừ batch mà không mở form phụ. |
| FR-012-011 | Các field target/user/drug/batch/notes vẫn tồn tại để lưu report. | Must | Presenter cũ vẫn đọc được `ed_user`, `cb_drug`, `ed_batch`, `ed_notes`, `sp_expected`. |

---

## 5. Yêu cầu phi chức năng cập nhật

| Mã | Nhóm | Yêu cầu |
|---|---|---|
| NFR-012-001 | Usability | Count workflow mặc định phải không bị chiếm chỗ bởi form nhập liệu. |
| NFR-012-002 | Usability | Keyboard phải phù hợp thao tác cảm ứng, không yêu cầu scroll để tìm phím. |
| NFR-012-003 | Visual design | Red accent phải dùng có chủ đích cho shutter, focus, danger và panel attention. |
| NFR-012-004 | Maintainability | Không phá API field hiện tại của `CountPage` để tránh sửa lớn `MainPresenter`. |
| NFR-012-005 | Stability | In-app overlay + keyboard không dùng native dialog nên không bị tách focus khỏi app. |

---

## 6. Thiết kế Count Screen v0.1.2

```text
┌──────────────────────────────────────────────────────────────┐
│ [READY] Camera counting · Tap Session only when needed       │
├───────────────┬──────────────────────────────────────────────┤
│ COUNT         │                                              │
│     062       │              CAMERA + OVERLAY                │
│ Total 154     │                                              │
│ Target 090    │                                              │
│ Δ +64         │                                              │
│ + current     │                                              │
│ − current     │                                              │
├───────────────┴──────────────────────────────────────────────┤
│   [ − ]   [ CAPTURE ]   [ + ]   [ Session ] [Undo] [Reset]   │
│                                      [Retake] [ COMPLETE ]    │
└──────────────────────────────────────────────────────────────┘
```

Session panel là floating widget:

```text
┌──────────────────────────────┐
│ SESSION                  ×   │
├──────────────────────────────┤
│ User                         │
│ Drug                         │
│ Batch                        │
│ Target                       │
│ Notes                        │
│ [Count] [Receive] [Dispense] │
│ QR / Share info              │
└──────────────────────────────┘
```

---

## 7. Thiết kế Virtual Keyboard v0.1.2

```text
┌──────────────────────────────────────────────────────────────┐
│ Input: Drug name   [preview text đang nhập]                  │
│ [Shift]                                      [Compact][Hide] │
├──────────────────────────────────────────────────────────────┤
│ 1 2 3 4 5 6 7 8 9 0                                      │
│ q w e r t y u i o p                                      │
│ a s d f g h j k l                                        │
│ Shift z x c v b n m ⌫                                    │
│ Clear        Space                         Done            │
└──────────────────────────────────────────────────────────────┘
```

Quy tắc:

- Không dùng scroll area trong keyboard chính.
- Chiều cao expanded cố định khoảng 360px.
- Compact mode vẫn còn nhưng không phải mặc định.
- Preview luôn thấy được.
- Hide là nút riêng, màu đỏ.

---

## 8. File thay đổi chính

| File | Thay đổi |
|---|---|
| `app/ui/widgets/virtual_keyboard.py` | Bỏ scroll area, tăng height, thêm preview rõ, Hide/Clear/Done, sửa auto-show focus. |
| `app/ui/widgets/app_overlay.py` | Dùng `QTimer.singleShot` để focus field sau khi overlay đã show. |
| `app/ui/pages/count_page.py` | Refactor Count Screen; Session chuyển thành floating panel overlay. |
| `app/ui/main_window.py` | Keyboard overlay lấy height từ widget, không hard-code 285px. |
| `resources/styles/app.qss` | Thêm style v0.1.2, red accent, floating panel, keyboard border/key border. |
| `app/core/constants.py` | Cập nhật version `v0.1.2`. |
| `README.md` | Cập nhật hướng dẫn v0.1.2. |
| `CHANGELOG.md` | Ghi thay đổi v0.1.2. |

---

## 9. Tiêu chí nghiệm thu v0.1.2

| Mã | Tiêu chí |
|---|---|
| AC-012-001 | `python -m compileall app` không báo lỗi cú pháp. |
| AC-012-002 | Gói release có thư mục gốc tên `pill_counter_v0_1_2`. |
| AC-012-003 | Count Screen không còn right Session card cố định. |
| AC-012-004 | Session panel mở dạng floating overlay khi nhấn Session. |
| AC-012-005 | Keyboard expanded height đủ để hiện toàn bộ key grid. |
| AC-012-006 | Keyboard có preview text, Hide, Clear, Done. |
| AC-012-007 | Form thêm/sửa thuốc trong overlay có thể focus field và gọi keyboard. |
| AC-012-008 | UI dùng red accent rõ hơn nhưng vẫn hài hòa trong palette medical. |

---

## 10. Ghi chú kiểm thử

Trong môi trường đóng gói hiện tại đã kiểm tra được mức cú pháp bằng `compileall`. Chưa thể kiểm thử runtime PyQt6/offscreen vì môi trường sandbox không có PyQt6. Kiểm thử phần cứng cần thực hiện trên Raspberry Pi 5 với màn hình 1024×600 và Logitech C930C.
