# Tóm tắt kiểm chứng

Hồ sơ công khai ghi source, artifact và phạm vi các kết quả đã đo. Log, RPC payload, đường dẫn tạm và lịch sử khảo sát được giữ local.

## Source final và baseline Fusion

Source final ở [accordion.scad](../accordion.scad), SHA-256 `37792d9628d1cc6f9b8b15056bf7e5d23239294ec1a6040a1951b3d9e620d5b4`. Thư viện [threads.scad](../threads.scad) có SHA-256 `42435bb118dba9e9c5e102dfdd417187ab1366b9dfcbcc6b49b694e7a38b3da2`. Artifact [exports/accordion.stl](../exports/accordion.stl) có SHA-256 `2ba95802e3db97be7956664c6b9389fe54987cdee7159392643261540b0a28c2`.

Bộ Fusion V4.2 dùng [input cố định](../fusion/AccordionV42/reference/) trước thay đổi female32:

- `accordion.scad`: SHA-256 `8f80b5382d7d36d020df508ff3d02a9bda6ee88b1fd4fec9c36ce78a013d3a57`.
- `threads.scad`: SHA-256 `42435bb118dba9e9c5e102dfdd417187ab1366b9dfcbcc6b49b694e7a38b3da2`.
- `accordion.stl`: SHA-256 `820485a4f9a147d9425e106d44faefb213f56c3d8eeb758a150e6e69cb247ee1`.

Source final có revision thân female mới hơn baseline này. Handoff, hash gate và test của Fusion đều trỏ input cố định bàn giao; kết quả native được gắn với đúng revision của nó.

## Kiểm tra offline

- Bộ Python hình học project: **47 test đạt**, chạy với OpenSCAD được cấu hình.
- Bộ Fusion V4.2 contract và fake orchestration: **68 test đạt** với input cố định.
- Mockup Node: **7 test đạt**.
- Python compilation và parse JSON handoff/validation đạt.

## Hồ sơ native W620

Hồ sơ trước đây ghi7 component definitions,7 body definitions,40 physical solid instances,10 physical thread instances,6 modeled native Thread definitions, timeline331 và0 unhealthy timeline item. F3D bàn giao cùng [bộ Fusion](../fusion/AccordionV42/README.md) thuộc baseline input cố định nêu trên.

## Các cổng tiếp theo

Native Fusion đối chiếu source final hiện hành, native ở width khác W620, so section/interference/pha ren đầy đủ, STEP/STL native mới và thử in/lắp/tải/độ bền vật lý giữ trạng thái `not_run`.
