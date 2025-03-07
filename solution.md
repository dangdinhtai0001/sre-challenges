### Mô Tả Giải Pháp

#### **Mục tiêu**
Đảm bảo hệ thống API Gateway có khả năng chống lại các cuộc tấn công Brute Force và DDOS bằng cách giới hạn số lượng request mà một client có thể gửi trong 1 giờ. Giải pháp phải:
- Xác định chính xác xem một request có vượt quá giới hạn rate limit (`R`) hay không.
- Đảm bảo hiệu suất cao khi xử lý các request theo thứ tự thời gian.

#### **Giải Pháp Chọn Lựa: Sliding Window Algorithm**
Lựa chọn thuật toán **Sliding Window** vì:
1. **Đơn Giản và Hiệu Quả**: Chỉ cần duy trì một danh sách (queue) các timestamp của các request nằm trong khung thời gian 1 giờ gần nhất, giảm thiểu độ phức tạp kiểm tra.
2. **Tính Chính Xác Cao**: Loại bỏ các timestamp cũ hơn `current_time - 3600` trước mỗi lần kiểm tra, đảm bảo chỉ tính toán trên các request hợp lệ.
3. **Hiệu Suất Tốt**: Queue với thao tác `popleft` giúp tối ưu kích thước và tránh lãng phí tài nguyên bộ nhớ. 

### Thuật Toán

#### Mô Tả Thuật Toán
Thuật toán rate limiting dựa trên cơ chế **Sliding Window** được triển khai như sau:

1. **Chuyển Đổi Timestamp**:
   - Chuyển đổi từng timestamp từ định dạng ISO-8601 sang epoch time (số giây kể từ ngày 1/1/1970) để dễ dàng so sánh và xử lý.

2. **Sử Dụng Queue**:
   - Sử dụng một queue (hàng đợi) để lưu trữ các timestamp của các request nằm trong khung thời gian 1 giờ gần nhất.

3. **Xử Lý Mỗi Request**:
   - Với mỗi request mới:
     - Loại bỏ tất cả các timestamp cũ hơn `current_time - 3600` khỏi queue.
     - Kiểm tra số lượng request còn lại trong queue:
       - Nếu số lượng ≥ `R`, từ chối request (`false`).
       - Ngược lại, chấp nhận request (`true`) và thêm timestamp của request hiện tại vào queue.

4. **Lưu Kết Quả**:
   - Lưu kết quả (`true/false`) cho mỗi request vào danh sách đầu ra.

---

#### Ví Dụ Minh Họa

Giả sử có input như sau:
```
10 3
2022-01-20T00:13:05Z
2022-01-20T00:27:31Z
2022-01-20T00:45:27Z
2022-01-20T01:00:49Z
2022-01-20T01:15:45Z
2022-01-20T01:20:01Z
2022-01-20T01:50:09Z
2022-01-20T01:52:15Z
2022-01-20T01:54:00Z
2022-01-20T02:00:00Z
```

##### Bước Xử Lý:
- **Request 1**: `2022-01-20T00:13:05Z` → Queue = `[00:13:05]` → Output: `true`
- **Request 2**: `2022-01-20T00:27:31Z` → Queue = `[00:13:05, 00:27:31]` → Output: `true`
- **Request 3**: `2022-01-20T00:45:27Z` → Queue = `[00:13:05, 00:27:31, 00:45:27]` → Output: `true`
- **Request 4**: `2022-01-20T01:00:49Z` → Loại bỏ `00:13:05` → Queue = `[00:27:31, 00:45:27, 01:00:49]` → Output: `false` (vượt quá `R = 3`)
- **Request 5**: `2022-01-20T01:15:45Z` → Loại bỏ `00:27:31` → Queue = `[00:45:27, 01:00:49, 01:15:45]` → Output: `true`
- **Request 6**: `2022-01-20T01:20:01Z` → Queue = `[00:45:27, 01:00:49, 01:15:45, 01:20:01]` → Output: `false` (vượt quá `R = 3`)
- **Request 7**: `2022-01-20T01:50:09Z` → Loại bỏ `00:45:27, 01:00:49, 01:15:45` → Queue = `[01:20:01, 01:50:09]` → Output: `true`
- **Request 8**: `2022-01-20T01:52:15Z` → Queue = `[01:20:01, 01:50:09, 01:52:15]` → Output: `true`
- **Request 9**: `2022-01-20T01:54:00Z` → Queue = `[01:20:01, 01:50:09, 01:52:15, 01:54:00]` → Output: `false` (vượt quá `R = 3`)
- **Request 10**: `2022-01-20T02:00:00Z` → Loại bỏ `01:20:01, 01:50:09, 01:52:15` → Queue = `[01:54:00, 02:00:00]` → Output: `false` (vượt quá `R = 3`)

##### Kết Quả:
```
true
true
true
false
true
false
true
true
false
false
```

#### Độ Phức Tạp

1. **Độ Phức Tạp Thời Gian**:
   - Mỗi request chỉ yêu cầu thực hiện hai thao tác chính:
     - Loại bỏ các timestamp cũ khỏi queue (`O(1)` trung bình nhờ tính chất của queue).
     - Kiểm tra độ dài queue (`O(1)`).
   - Tổng độ phức tạp cho `N` request là **O(N)**.

2. **Độ Phức Tạp Không Gian**:
   - Queue chỉ lưu trữ tối đa `R` timestamp tại bất kỳ thời điểm nào.
   - Độ phức tạp không gian là **O(R)**.

### Hướng dẫn Thực Thi Code

#### **Cấu Trúc source code**
- `main.py`: File chứa mã nguồn chính để thực hiện rate limiting.
- `test/inputX.txt`: Các file input chứa dữ liệu đầu vào cho các test case.
- `output.txt`: File lưu trữ kết quả sau khi chương trình được chạy.

---

#### **Cách Chạy Chương Trình**

1. **Chuẩn Bị File Input**:
   Đảm bảo file input (ví dụ: `test/input1.txt`) đã được chuẩn bị đúng định dạng:
   ```
   N R
   timestamp1
   timestamp2
   ...
   timestampN
   ```
   - Dòng đầu tiên chứa hai số nguyên `N` (số lượng request) và `R` (giới hạn rate limit).
   - Các dòng tiếp theo là các timestamp ở định dạng ISO-8601.

2. **Thực Thi Chương Trình**:
   - Mở terminal và di chuyển đến thư mục chứa source code.
   - Chạy lệnh sau để thực thi chương trình:
     ```bash
     python main.py
     ```

3. **Kiểm Tra Kết Quả**:
   - Sau khi chương trình hoàn thành, mở file `output.txt` để xem kết quả.
   - Mỗi dòng trong file này chứa giá trị `true` hoặc `false`, tương ứng với việc mỗi request được chấp nhận (`true`) hoặc từ chối (`false`).

---

#### **Lưu Ý**
- Đảm bảo rằng Python đã được cài đặt trên hệ thống và phiên bản Python >= 3.6 để hỗ trợ các tính năng như `datetime.fromisoformat`.
- Nếu muốn thay đổi test case, chỉ cần cập nhật đường dẫn file input trong biến `input_file_path` trong file `main.py`.


### Kết Luận

#### **Đánh Giá Giải Pháp**
- **Ưu Điểm**:
  - **Chính Xác**: Thuật toán **Sliding Window** đảm bảo tính toán chỉ trong khung thời gian 1 giờ, đáp ứng yêu cầu rate limiting.
  - **Hiệu Suất**: Độ phức tạp **O(N)** về thời gian và **O(R)** về không gian, phù hợp xử lý số lượng request lớn.
  - **Đơn Giản**: Code gọn gàng, dễ triển khai và mở rộng.

#### **Nhược Điểm & Cải Tiến**
1. **Hỗ Trợ Nhiều Client**: Hiện chỉ áp dụng cho một client; có thể dùng **hash table** để quản lý queue riêng biệt theo ID client.
2. **Đồng Bộ Thời Gian**: Cần sử dụng **NTP** nếu có chênh lệch thời gian giữa máy chủ và client.
3. **Tối Ưu Hóa**: Có thể thay `deque` bằng **circular buffer** để tiết kiệm bộ nhớ.
4. **Phân Tán**: Sử dụng **Redis** (hoặc các giải pháp tương tự ) để đồng bộ rate limit trong hệ thống phân tán.

Giải pháp hiện tại hiệu quả nhưng cần cải tiến để đáp ứng yêu cầu phức tạp hơn.