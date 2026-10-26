# Cụm cửa gấp — mockup tương tác

Mở bằng máy chủ HTTP từ thư mục gốc repo. Cài Three.js đúng phiên bản trong `package.json`, rồi chạy:

```powershell
Set-Location .\mockup
npm install --ignore-scripts --no-audit --no-fund
python -m http.server 8765 --bind 127.0.0.1 --directory ..
```

Mở `http://127.0.0.1:8765/mockup/`. Bộ kiểm tra động học dùng Node tích hợp của Codex trên máy này:

```powershell
node --test
```

Mô hình dùng đơn vị mm. Mười hai lá gấp tạo mười ba trục xen kẽ ở tư thế minh họa; mười hai khoảng trục bản lề giữ 42 mm. Mỗi lá rộng ngoài danh nghĩa 50 mm, gồm khoảng trục 42 mm và hai bán kính tang bản lề 4 mm. Hai trục biên cách mép 10 mm. Thanh trái dài 175 mm, từ x=10 tới x=185. Đoạn nối dài 230 mm, miệng tại x=160, đầu ren tại x=390. Ống cái vẫn dài 140 mm và kết thúc ở mép phải. Phần ăn khớp danh nghĩa là `530 − chiều rộng`: 100 / 65 / 30 mm tại 430 / 465 / 500 mm. Số vòng là chênh lệch phần ăn khớp so với cấu hình 500 mm, chia bước ren 4 mm. Rotor quay theo số vòng đó. Bật “Mặt cắt PIP” để xem hai mặt côn giữ và khe hướng kính. Chiều cao trong mockup vẫn là hình minh họa 200 mm; lá in trong CAD cao 250 mm.

Đây là tư thế gấp đều để minh họa hình học. Cụm chưa có liên kết đồng bộ ray, nên mô hình không chứng minh chuyển động thực, lực, độ võng, độ bền, dung sai in hay khả năng lắp.

## Khớp phải in liền tại chỗ (PIP)

Đầu phải dùng rotor captive in cùng lần: rotor dài 140 mm, gồm thân 130 mm và đuôi khớp 10 mm tới mép ngoài `W`. Vòng cố định đồng tâm trục `X=W-10, Y=100, Z=-30`, bán kính ngoài 20 mm; lòng vòng theo profile `X=-3..10` có các bán kính 12.6, 12.6, 16.6, 12.6, 12.6 mm. Web cố định nối vòng vào tấm biên. Rotor và vòng tạo hai mặt côn 45 độ giữ dọc trục, với khe hướng kính danh nghĩa 0.6 mm. Mặt cắt trong mockup để thấy hai mặt côn và khe này.

Đây là kích thước mockup, chưa xác nhận trên slicer, support, hướng in, khe quay, độ bền hay mẫu in/lắp thực tế.

Đường xoắn ren trong mockup chỉ minh họa vị trí ren; không phải biên dạng ren CAD. Tham số ren chung `thread_offset=-0.25 mm` dùng cho cả hai thanh. Lòng trơn là minor TR20×4 7H, `R8.09375` (Ø16.1875). Đoạn ren minh họa dài 118 mm, sau đó là cổ trơn.
