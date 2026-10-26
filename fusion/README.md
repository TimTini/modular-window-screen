# Accordion V4.2 — Autodesk Fusion

Bộ script công khai nằm trong [AccordionV42](AccordionV42/README.md). Builder dựng baseline V4.2 **trước thay đổi female32**, với bộ input cố định trong [reference](AccordionV42/reference/). Các hash source và mesh của baseline được kiểm tra trước khi dựng.

Source `accordion.scad` ở gốc project là bản final mới hơn, đã thay đổi thân female rotor. Native evidence của bộ Fusion thuộc baseline cố định; việc dựng Fusion theo bản final hiện hành giữ trạng thái `not_run`.

## Chạy script

1. Giữ nguyên thư mục `AccordionV42`, gồm Python, manifest, thư mục reference và handoff.
2. Trong Fusion, mở **Utilities → Add-Ins → Scripts and Add-Ins → Scripts → +** và chọn thư mục này.
3. Chạy **AccordionV42**. Width được chọn qua `RUN_WIDTH_MM` rồi chạy lại để dựng topology.
4. Hai User Parameters có thể đổi trong document là `thread_offset` và `male_bore_d`; các RUN_VALUES khác dùng cơ chế rebuild được mô tả tại README của bộ.

## Kiểm chứng

- Bộ offline gồm **68 test** contract và orchestration, đã chạy với bộ input cố định bàn giao.
- Hồ sơ native W620 trước đây ghi40 solid instances,7 component/body definitions,10 physical thread segments,6 modeled Thread definitions, timeline331 và0 timeline issue.
- [Handoff](AccordionV42/handoff.json), [hồ sơ W620](AccordionV42/validation/runtime-W620.json) và [tóm tắt kiểm chứng project](../docs/VALIDATION.md) giữ phạm vi các kết quả này.

Chạy tại gốc project:

```powershell
python -m unittest discover -s fusion/AccordionV42/tests
```

Bản Accordion V4.1 và hồ sơ làm việc cũ được giữ local. Ma trận native ở width khác W620, đồng bộ native với source final, đối chiếu section/interference/pha ren đầy đủ, STEP/STL native mới và thử in/lắp vật lý giữ trạng thái `not_run`.
