# SCAD V4.2 — FINAL

Ngày chốt: **2026-10-22**; cập nhật thân female **2026-10-23**, theo phương án người dùng đã duyệt.

## Nguồn final

- File mở chính: [accordion.scad](accordion.scad), nằm ngay tại gốc dự án.
- Thư viện đi cùng: [threads.scad](threads.scad), giữ cùng thư mục với file chính.
- Nền hình học có hai sống gá chung dày10 mm, giữ hai mặt đáy theo cơ cấu ren hiện tại. Revision hiện hành thu thân female về Ø32 và thêm chân liền chạm bàn; nhận diện bằng SHA-256 bên dưới.
- Thư viện ren đi cùng được nhận diện bằng SHA-256 bên dưới. Git gốc và các mốc thiết kế trung gian được giữ trong hồ sơ local.
- Các bản lưu cũ ở thư mục `archive/`; các file dưới `work/` phục vụ chẩn đoán và lưu bằng chứng. Cặp nguồn final được chỉ định là hai file gốc nêu trên.

SHA-256 của nguồn được chốt:

```text
accordion.scad
37792d9628d1cc6f9b8b15056bf7e5d23239294ec1a6040a1951b3d9e620d5b4

threads.scad
42435bb118dba9e9c5e102dfdd417187ab1366b9dfcbcc6b49b694e7a38b3da2
```

## Cấu hình mặc định

- `part="display"`, `W=620`, `H=250`, `clamp_travel=0`.
- 16 lá xếp,17 chốt bản lề và2 bộ đoạn nối; mỗi đoạn nối gồm socket và trục in riêng.
- `support_web_width=10`, `male_bore_d=2`, `thread_offset=-0.25`.
- `thread_socket_outer_r=16`: thân female và socket CT09 cùng Ø32; `female_foot_width=9` tạo chân liền chạm bàn, hai sườn dưới45°. Vành giữ Ø36, eo Ø21, khe PIP0,6, ren trong118 và tổng dài139,5 mm giữ nguyên. Đoạn chuyển tiếp4 mm kết thúc trước vùng V.
- Dải cấu hình nguồn: W430–1000 mm; chi tiết in theo bàn250 mm.

## Bằng chứng gắn với mốc nguồn

Đã chạy lại toàn bộ47 unittest trên revision hiện hành, exit0. Hồ sơ local ghi phép đo STL female: một mesh kín, thân rộng32, chân rộng9, minZ sau đặt in=0; thành nhỏ nhất trong các mặt cắt kiểm tra4,915 mm. Thể tích riêng female giảm23,594% so với nền local trước thay đổi thân female. Kiểm72 góc quay đạt ngưỡng giao; đối chứng kéo trục có giao dương. Wall là phép đo mặt cắt mesh; phép đo chiều dày theo pháp tuyến toàn bộ bề mặt có phạm vi riêng.

Full build exit0 với212 probe,16 bề rộng W430–1000 và17 tư thế siết trên cùng bộ W620. Assembly đã xuất lại đủ40 chi tiết vật lý. Kiểm trực tiếp named volume của3MF cặp phải: cả female và gá đều là mesh kín, minZ=0; thân female32 và chân9 đúng trên file giao. Cặp in có bao140×250×51,9 mm. Cắt lớp với profile bàn250: không có đường đùn support, tọa độ đùn nằm trong bàn; vẫn có cảnh báo `Collapsing overhang, Low bed adhesion`. Vùng gờ bridge cũ dưới tai phải còn0 move; gate này chỉ kiểm vùng đã định vị.

- [Assembly3MF đủ40 chi tiết](exports/accordion.3mf), [AssemblySTL](exports/accordion.stl).
- [3MF in cặp gá phải/female đúng tư thế](exports/parts/right-pip.3mf).

- [Tóm tắt kiểm chứng, hash nguồn và phạm vi native](docs/VALIDATION.md).
- Các report đo female, kiểm3MF, kiểm rotor và runbook chi tiết thuộc hồ sơ local của checkpoint; bản công khai bàn giao source, artifact và các test tái chạy được.

Trạng thái FINAL áp dụng cho nguồn SCAD này. Slicer vẫn có cảnh báo ở cặp phải; chưa có bằng chứng in thực tế, thử lực hoặc độ bền. Thay tham số hoặc sửa nguồn tạo cấu hình mới cần xuất và kiểm lại theo runbook.
