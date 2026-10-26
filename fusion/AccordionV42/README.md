# Accordion V4.2 Fusion package

Gói này dựng source `accordion.scad` thành assembly native parametric trong
Fusion. Đơn vị source là mm; conversion sang cm của Fusion chỉ xảy ra ở biên
native builder. `exports/accordion.stl` chỉ là mesh tham chiếu.

## Baseline và handoff

Baseline là `W=620 mm`, `H=250 mm`, `clamp_travel=0 mm`. Source hashes và
contract được ghi trong [handoff.json](handoff.json). Handoff đã xác minh:

Gói này mang theo một input snapshot độc lập trong [`reference/`](reference/):
`accordion.scad`, `threads.scad` và mesh tham chiếu `accordion.stl` đều là bản
V4.2 pinned pre-female32 dùng cho các bằng chứng Fusion bên dưới. Source
`../../accordion.scad` ở gốc project hiện là revision final muộn hơn, có thay
đổi hình học female body; nó không được tráo vào handoff này và chưa được
Fusion V4.2 runtime xác minh cùng contract cũ.

- 7 component definitions và 7 body definitions dự kiến.
- 40 occurrence/print pieces.
- 10 physical thread segments trong assembly source.
- 6 native Thread feature definitions dự kiến: một ở left support, một ở
  female rotor, hai ở mỗi rod socket và hai ở mỗi rod shaft.

Mười physical segments là các instance của assembly. Sáu Thread definitions
là số feature trên các component definition duy nhất. Fusion **2705.1.30** đã
chạy W620: **40 solid instances, 7 body definitions, 6 modeled Thread features,
10 Thread instances, timeline 331, không có item lỗi/cảnh báo, 0 mesh và 0 base feature**.
Xem [audit runtime](validation/runtime-W620.json) và [thử tham số](validation/parameters-W620.json).

## Cài và chạy trong Fusion

Bàn giao trực tiếp thư mục script và file F3D. Chỉ đóng gói/nén dự án khi có
yêu cầu riêng; xác minh F3D bằng Fusion import/readback.

1. Mở **Utilities > Add-Ins > Scripts and Add-Ins > Scripts**.
2. Thêm thư mục `fusion/AccordionV42` làm script folder.
3. Chạy **AccordionV42**. Mỗi lần chạy tạo một document V4.2 mới, chưa lưu.
4. Đổi `RUN_WIDTH_MM` trong `AccordionV42.py` trước khi chạy lại. W là
   Run-only; mỗi thay đổi W phải dựng lại topology, chiều dài, placement và
   phase theo source.

Đã xuất và mở lại [F3D W620](exports/AccordionV42-W620.f3d) trong Fusion:
40 solid instances, timeline 331, không có item lỗi/cảnh báo.
STEP/STL từ Fusion và ma trận runtime các W khác chưa chạy.

## Change Parameters hiện thực

Hai User Parameters được tạo trong Change Parameters:

| Parameter | Mặc định | Miền source |
|---|---:|---|
| `thread_offset` | -0.25 mm | -0.4..-0.1 mm |
| `male_bore_d` | 2 mm | dương và giữ các guard thành ren source |

`clamp_travel_mm`, `pip_gap_mm`, `leaf_bottom_mm`, `leaf_top_mm`,
`joint_angle_deg` và `support_web_width_mm` là `RUN_VALUES` rebuild-only.
Đổi các giá trị này rồi chạy lại script để dựng lại sketch, biên dạng PIP và
placement. `support_web_width_mm` mặc định 10 mm, tối thiểu 10 mm.
`male_bore_d` điều khiển dimension đường kính của lỗ; `thread_offset` điều
khiển Offset Face và dimension mặt cắt đáy socket theo công thức giữ thành
2 mm. Đã thử live `male_bore_d` 2→3→2 mm: bán kính lỗ thực tăng từ 1 lên
1,5 mm. Đổi `thread_offset` −0,25→−0,4→−0,25 mm: đáy socket đổi tới Y=−12,65 mm,
giữ thành danh nghĩa 2 mm. Phục hồi baseline giữ thể tích sai khác dưới 0,01 mm³
và không có item lỗi/cảnh báo. Chỉnh sửa trực tiếp ngoài miền source là unsupported.

## Kiểm tra offline

Từ project root chạy:

```powershell
python -m unittest discover -s fusion/AccordionV42/tests -v
python -m compileall -q fusion/AccordionV42
```

Khi chuyển máy, dùng Python 3 trong `PATH` hoặc đặt đường dẫn thực thi riêng
trước khi chạy các lệnh trên.

`test_handoff.py` kiểm tra hash source/STL, baseline counts, mười thread roles,
hai live parameters, W Run-only và các trạng thái evidence. Các test fake chỉ
xác minh orchestration/contract; chúng không thay thế Fusion kernel runtime.

## Sửa lỗi review ngày 2026-10-22

- Côn rotor dùng bán kính 18/10,5 mm, đúng đường kính Ø36/Ø21 của source.
- Thân socket dừng tại đầu đoạn ren sau; hai phần nối tại mặt đầu, không
  chồng vật liệu làm lấp rãnh ren sau.
- Dao cắt vát web được đặt theo đáy và hai đầu Y=0/H; chân ren trái giữ X=-10 mm.
- Sketch lỗ có driving diameter dimension; mặt cắt đáy socket theo `thread_offset`.
- Web width đổi qua Run/rebuild để cập nhật cả sketch và biên dạng PIP.

Regression gọi builder thật và ghi nhận primitive/dimension. Lượt runtime
tiếp theo còn sửa bootstrap import từ thư mục script, pivot Point3D, alias
bản lề, cổ pin, move bằng trục proxy/component space và thứ tự nhân ma trận.
Clip ren trái trước khi join sole tránh lỗi ASM_BAD_CONTAINMENT và giữ nguyên
solid cuối. Native W620, Join socket, Thread metadata và hai ca đổi tham số
đã chạy thành công. Loft/hull riêng khác cách dựng nhưng chưa tìm thấy sai
khác khối cuối ngoài vùng foot/web đã union.

Trạng thái hiện tại: 68 test offline `pass`; native W620, hai ca recompute,
F3D export/readback `pass`. So sánh đầy đủ section/interference/pha ren giữa
SCAD/Fusion, ma trận native các W khác, STEP/STL và physical vẫn `not_run`.
