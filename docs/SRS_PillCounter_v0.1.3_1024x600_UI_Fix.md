# SRS - Pill Counter v0.1.3 1024×600 UI Fix

**Tên dự án:** Pill Counter  
**Phiên bản:** v0.1.3  
**Gói release:** `pill_counter_v0_1_3.zip`  
**Mục tiêu chính:** sửa lỗi chồng lấn giao diện Count Screen và bàn phím ảo trên màn hình thật 7 inch 1024×600.

## 1. Bối cảnh

Sau bản v0.1.2, giao diện đã tiến gần hơn đến phong cách camera-app/PharmCam/VIVID nhưng vẫn còn lỗi khi chạy trên màn hình thật 1024×600:

- Count Screen vẫn bị chồng lấn do preview/các panel/nút chưa được ràng buộc theo kích thước thực tế.
- Người dùng chốt lại rằng preview camera phải cố định **640×480**.
- Header/taskbar cho nút Menu chiếm quá nhiều diện tích dọc.
- Nút và chữ trong Count Screen cần nhỏ lại để phù hợp 7 inch.
- Virtual keyboard vẫn bị chồng phím.

## 2. Mục tiêu v0.1.3

1. Cố định camera preview ở **640×480**.
2. Tối ưu toàn bộ Count Screen cho không gian **1024×600**.
3. Bỏ header/taskbar lớn trên các screen chức năng.
4. Dùng nút menu nổi nhỏ, bán trong suốt, ở góc phải.
5. Giảm kích thước chữ và nút trong Count Screen.
6. Làm keyboard thấp hơn, ít hàng hơn, không chồng phím.
7. Giữ bảng màu medical palette đã chốt.
8. Không thay đổi lõi inference/model/database/report nếu không cần thiết.

## 3. Yêu cầu chức năng cập nhật

| Mã | Yêu cầu | Ưu tiên | Tiêu chí nghiệm thu |
|---|---|---|---|
| FR-013-001 | Count Screen phải hiển thị preview camera cố định 640×480. | Must | `QLabel preview` có fixed size 640×480. |
| FR-013-002 | Count Screen phải không cần header/taskbar chiếm chiều cao. | Must | Header hidden trên các màn hình chức năng. |
| FR-013-003 | App phải có nút menu nổi nhỏ ở góc phải. | Must | Nút `☰` overlay 44×38, không làm thay đổi layout. |
| FR-013-004 | Count Screen phải chia thành 3 vùng: metrics, camera preview, action rail. | Must | Tổng layout không vượt 1024×600. |
| FR-013-005 | Session panel chỉ hiện khi người dùng bấm Session/Verify. | Must | Session panel là overlay, không chiếm layout mặc định. |
| FR-013-006 | Keyboard phải dùng layout thấp, không cần scroll, không chồng phím. | Must | Keyboard 4 hàng phím, chiều cao khoảng 246 px. |
| FR-013-007 | Keyboard phải giữ preview text và nút Hide. | Must | Header keyboard có context, preview, Hide. |
| FR-013-008 | Các nút Count Screen phải nhỏ hơn v0.1.2 nhưng vẫn đủ chạm. | Should | Button chính 38–56 px cao. |

## 4. Thiết kế Count Screen

Kích thước mục tiêu:

```text
Screen: 1024×600
Preview camera: 640×480 fixed
Left metrics panel: ~168×488
Right action rail: ~184×488
Floating menu button: 44×38 overlay, top-right
```

Bố cục:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ Count metrics │        Fixed camera preview 640×480        │ Actions   │ ☰
│ 168×488       │        centered in camera card              │ 184×488   │
├────────────────────────────────────────────────────────────────────────┤
│ Bottom hint/status strip, compact                                      │
└────────────────────────────────────────────────────────────────────────┘
```

## 5. Thiết kế keyboard v0.1.3

Keyboard không dùng 5 hàng lớn như v0.1.2 nữa. Layout mới:

```text
[Context] [Preview text] [Shift] [Small/Full] [Hide]
------------------------------------------------------
1 2 3 4 5 6 7 8 9 0
q w e r t y u i o p
a s d f g h j k l ⌫
z x c v b n m Clr Space Done
```

Chiều cao mặc định: khoảng 246 px.  
Chế độ compact: khoảng 208 px.

## 6. File thay đổi chính

| File | Thay đổi |
|---|---|
| `app/ui/pages/count_page.py` | Rebuild Count Screen với fixed 640×480 preview và action rail. |
| `app/ui/main_window.py` | Ẩn header, thêm floating menu button overlay. |
| `app/ui/widgets/virtual_keyboard.py` | Rebuild keyboard 4 hàng, thấp hơn, không scroll/chồng phím. |
| `resources/styles/app.qss` | Thêm style v0.1.3 cho 1024×600, floating menu, compact keyboard. |
| `app/core/constants.py` | Cập nhật version v0.1.3. |
| `config.json` | Camera width/height 640×480, profile `fixed_640x480`. |

## 7. Tiêu chí nghiệm thu

| Mã | Tiêu chí |
|---|---|
| AC-013-001 | Chạy app ở 1024×600, Count Screen không chồng lấn. |
| AC-013-002 | Camera preview đúng vùng 640×480. |
| AC-013-003 | Không còn header/taskbar lớn trên Count Screen. |
| AC-013-004 | Nút menu nổi xuất hiện ở góc phải, không đẩy layout. |
| AC-013-005 | Các nút trong action rail không chồng nhau. |
| AC-013-006 | Keyboard hiện lên không chồng phím và không cần scroll. |
| AC-013-007 | Keyboard vẫn nhập được vào field trong Session popup và overlay form. |
| AC-013-008 | Package có thư mục gốc `pill_counter_v0_1_3`. |

## 8. Ghi chú kiểm thử

Trong môi trường đóng gói hiện tại chỉ kiểm tra được cú pháp Python bằng:

```bash
python3 -m compileall -q app
```

Cần kiểm thử runtime thật trên Raspberry Pi 5 + Waveshare 7 inch 1024×600 + camera C930C để xác nhận pixel-perfect layout.
