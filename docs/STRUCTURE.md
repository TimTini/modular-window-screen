# Cấu trúc dự án modular-window-screen

Điểm bắt đầu: [README](../README.md). Source chính và script chạy giữ ở thư mục gốc. Chuẩn thư mục áp dụng ngày 26/10/2026.

## File và thư mục hiện có

Source: `accordion.scad; threads.scad`.

- [exports/](../exports/): đầu ra CAD, preview và report theo pipeline.
- [docs/](../docs/): tài liệu project và ảnh minh họa.
- [fusion/](../fusion/): script/manifest, hướng dẫn và test Fusion.
- [mockup/](../mockup/): ứng dụng xem thử.
- [tests/](../tests/): kiểm thử project.
- `verification/`: cấu hình và công cụ kiểm chứng local, không thuộc public allowlist.
- `work/`: checkpoint và khảo sát local, không thuộc public allowlist.
- `archive/`: phiên bản lịch sử được giữ local; bản công khai dùng source final và baseline Fusion được ghi rõ.

FINAL.md và README xác định revision đang dùng. archive giữ lịch sử; mockup và verification có pipeline riêng. Thư mục Fusion giữ các revision đã được ghi rõ trong README của nó.

## Quy ước dùng chung

- `exports/` chứa đầu ra; README/manifest xác định bộ hiện hành và revision nguồn.
- `fusion/AccordionV42/reference/` chứa input V4.2 pinned và provenance đã được kiểm tra; `assets/` giữ tài nguyên runtime khi có.
- `docs/` chứa tài liệu, `work/` chứa checkpoint/khảo sát local, `work/tmp/` chứa file thử và `backups/` chứa snapshot khi cần. Thư mục được tạo theo dữ liệu thực tế.
- `archive/` giữ phiên bản lịch sử khi project dùng cơ chế đó. Các thư mục chuyên biệt tiếp tục theo pipeline hiện có.
- Kiểm source/đường dẫn, render, native Fusion, slicer và thử vật lý có trạng thái bằng chứng riêng trong hồ sơ kỹ thuật.

## Tra đường dẫn lịch sử

Các vị trí dữ liệu hiện tại được giữ trong đợt chuẩn hóa này. Report, snapshot và log cũ giữ thông tin tại thời điểm chạy; áp dụng bản đồ trên khi tra locator cũ. Tài liệu và script đang dùng tham chiếu vị trí hiện hành.
