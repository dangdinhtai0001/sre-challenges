## Phạm vi giải pháp

**Mục tiêu**
Thiết kế hệ thống **API Gateway** trên **Kubernetes** với **rate limit tập trung**, đảm bảo tính nhất quán dù có nhiều instance chạy.  

**Đối tượng áp dụng**  
- Hệ thống hiện có trên Kubernetes, sử dụng cluster để mở rộng.  
- Các instance Gateway cần chia sẻ trạng thái rate limit để tránh trùng lặp giới hạn.  

### **Các yêu cầu chính**  
1. **Giới hạn tốc độ tập trung**: Dữ liệu rate limit được quản lý bởi dịch vụ trung tâm (ví dụ: Redis), không phụ thuộc vào instance Gateway.  
2. **Tính sẵn sàng cao**: Hoạt động ổn định khi dịch vụ trung tâm hoặc instance Gateway fail (dùng fallback như tạm cho phép request vượt limit).  
3. **Tối ưu Kubernetes**: Tận dụng tính năng của Kubernetes (Deployment, Service, ConfigMap) để triển khai tự động và scale linh hoạt.  


## Phân tích yêu cầu  

### Vấn đề cần giải quyết
- **Trùng lặp rate limit**: Khi nhiều instance Gateway chạy độc lập, mỗi instance tự quản lý rate limit → **không đảm bảo tổng số request của client/IP không vượt giới hạn toàn hệ thống** (ví dụ: client gửi request đến 2 instance khác nhau → mỗi instance tính riêng, dẫn đến tổng request vượt limit).  
- **Thiếu trạng thái chung**: Cần **dữ liệu rate limit tập trung** để tất cả instance truy cập và cập nhật đồng bộ, tránh mất đồng nhất.  

### **Yêu cầu kỹ thuật**  
1. **Độ trễ thấp**  
   - Thao tác kiểm tra giới hạn (ví dụ: tăng counter, so sánh với limit) phải **nhanh** (~ <1ms) để không làm chậm request.  
2. **Quy mô mở rộng**  
   - Hỗ trợ hàng nghìn request/giây mà không gây bottleneck.  
3. **Tính nhất quán**  
   - Tránh tranh chấp cập nhật dữ liệu khi nhiều instance cùng truy cập/trường hợp key rate limit.  
4. **Bảo mật**  
   - Dữ liệu rate limit (ví dụ: Redis) cần được bảo vệ khỏi truy cập trái phép.  

### **Yếu tố rủi ro**  
1. **Redis down**  
   - Nếu dịch vụ lưu trữ trạng thái (ví dụ: Redis) fail, hệ thống không thể kiểm soát rate limit → **có thể bị tấn công DDoS**.  
2. **clock synchronization**  
   - Các instance Gateway cần đồng bộ thời gian để tính toán window time (ví dụ: 60s) chính xác.  

## Kiến trúc tổng thể

### **Cấu trúc tổng quan**  
Dựa trên **mô hình tập trung**, hệ thống sử dụng **Redis Cluster** làm "trung tâm" lưu trữ trạng thái rate limit. Các instance Gateway truy vấn Redis để kiểm tra giới hạn và cập nhật trạng thái. Kiến trúc đảm bảo **scalability** và **fault tolerance** trên Kubernetes.  

### **Các thành phần chính**  
1. **API Gateway Cluster**  
   - **Vai trò**: Tiếp nhận request, kiểm tra rate limit, và điều hướng đến service đích.  
   - **Triển khai**: Chạy dưới dạng **Deployment/Service** trên Kubernetes, dễ scale in/out.  
   - **Kết nối**: Gửi request đến Redis để lấy/trường hợp rate limit.  

2. **Redis Cluster**  
   - **Vai trò**: Lưu trữ trạng thái rate limit (ví dụ: số request của client/IP trong window time).  
   - **Tính năng**:  
     - **HA**: Đa node, tự động failover.  
     - **Sharding**: Phân tán key để xử lý load cao.  
   - **Dữ liệu**: Sử dụng **Hash/String** để lưu thông tin rate limit.  

3. **Circuit Breaker & Fallback**  
   - **Vai trò**: Xử lý trường hợp Redis không phản hồi (ví dụ: timeout, down).  
   - **Cơ chế**:  
     - Chuyển sang **local cache** tạm thời cho phép request vượt limit trong một khoảng thời gian (ví dụ: 10s).  
     - Ghi log sự kiện để giám sát.  

4. **Monitoring & Logging**  
   - **Vai trò**: Theo dõi hiệu suất hệ thống và phát hiện lỗi.  
   - **Dữ liệu theo dõi**:  
     - Độ trễ Redis, rate limit violations, số instance Gateway đang chạy.  


## Chi tiết thiết kế

### Rate Limiting Logic 

#### Lưu trữ trạng thái  
- **Key**: `rate:{user_id/IP}:{window}` (ví dụ: `rate:user123:60s`).  
- **Tại sao dùng Redis**:  
  - Tốc độ cao nhờ lệnh atomic (`INCR`, `EXPIRE`).  
  - Chia sẻ trạng thái giữa các instance Gateway.  
  - Tự động phân phối key qua Redis Cluster.  

#### Kiểm tra giới hạn 
1. **Tăng counter**: `INCR rate:user123:60s` → atomic, tránh race condition.  
2. **So sánh giá trị**: Nếu > giới hạn → từ chối request.  
3. **Đặt TTL**: `EXPIRE rate:user123:60s 60` → chỉ cần set 1 lần khi tạo key.  

#### Tính nhất quán 
- Kết hợp `INCR` và `EXPIRE` trong **transaction Redis** (`MULTI/EXEC`) để đảm bảo atomicity.  
- Trường hợp key mới: Tạo key + set TTL trong cùng transaction.  

### Key Sharding  

#### Tại sao cần Key Sharding?
- **Vấn đề**: Khi số lượng user/IP tăng, nếu lưu trữ tất cả key trên một node Redis → **bottleneck** ảnh hưởng đến khả năng mở rộng.  
- 
- **Giải pháp**: Sử dụng **Redis Cluster** để **tự động phân phối key** (sharding) lên nhiều node, đảm bảo:  
  - **Cân bằng tải**: Tận dụng tài nguyên của nhiều node.  
  - **Độ trễ thấp**: Truy vấn key không bị tập trung vào một điểm.  

#### Thiết kế key tối ưu sharding
- Định dạng: `rate:{user_id/IP}:{window_time}` (ví dụ: `rate:user123:60s`).  
- Lợi ích:  
  - Phân vùng tự động nhờ **consistent hashing** của Redis Cluster.  
  - Nhóm key cùng user/IP vào shard duy nhất, tránh truy vấn phân tán.  

**Ưu điểm**  
1. **Mở rộng**: Thêm node tăng capacity lưu trữ và xử lý.  
2. **Nhất quán**: Key cùng user/IP trên shard duy nhất → tránh race condition.  
3. **Triển khai trên Kubernetes**: Dễ dàng với **statefulset/headless service**.  

**Sliding window time**  
- **Phương pháp**: Chia window lớn thành nhiều window nhỏ (ví dụ: 2 window 30s thay vì 1 window 60s).  
- **Tính toán**: Tổng counter của window đang active → giảm spike traffic.  
- **Ví dụ**: Window 60s → 2 window 30s có TTL 30s.  

**Lưu ý triển khai**  
- **Tránh hot key**: Chia nhỏ key theo thời gian nếu traffic user/IP quá lớn.  
- **Transaction**: Chỉ dùng cho key cùng shard (tránh lệnh MULTI/EXEC đa shard). 

### Xử lý lỗi & fallback  

#### Khi Redis sập 
- **Giải pháp**:  
  - **Circuit Breaker** (Resilience4j/CircuitBreaker/...) → mở circuit khi Redis lỗi liên tiếp.  
  - **Fallback**: Dùng **local cache** trên mỗi instance Gateway để lưu counter tạm với mức giới hạn cao hơn (ví dụ: 200 req/10s).  

#### Local cache  
- **Triển khai**:  
  - Lưu key `{user_id/IP}:{window}` trong memory với TTL ngắn (ví dụ: 10s).  
  - Không đồng bộ với Redis → ưu tiên tốc độ và sẵn sàng.  
- **Phục hồi**: Xóa cache và quay về Redis khi hệ thống bình thường.  

#### Burst request
- Áp dụng **sliding window** trên local cache → cho phép vượt giới hạn tạm để đảm bảo sẵn sàng.  

#### Phục hồi Redis 
- Circuit Breaker chuyển sang **half-open** → test Redis → đóng circuit nếu thành công.  

#### Ưu điểm  
- Mỗi instance tự quản lý local cache → không chia sẻ.  
- Khi Redis up lại → reset cache và đồng bộ trạng thái.  

### Phương án scaling

#### Mở rộng Redis Cluster
- **Phương án**: Thêm node qua `redis-cli cluster meet` hoặc tăng replicas trên Kubernetes → Redis tự rebalance data.  
- **Lợi ích**: Tăng throughput, đảm bảo HA.  

#### **Mở rộng Gateway**  
- **Cách thực**: Dùng **HPA** trên Kubernetes scale instance dựa trên CPU/memory hoặc metrics request.  
- **Lợi ích**: Đáp ứng traffic đột biến, giữ tính nhất quán nhờ chia sẻ Redis.  

#### **Tối ưu Redis**  
1. **Phân vùng key**: Định dạng `{user_id/IP}:{window}` → distribute đều node.  
2. **Redis modules**:  
   - **RedisTimeSeries**: Quản lý window time theo timestamp.  
   - **RedisJSON/RediSearch**: Tối ưu query phức tạp.  
3. **Connection pooling**: Reuse connection để giảm độ trễ.  

## Kết luận

- **Giải pháp** tập trung vào việc sử dụng **Redis Cluster** như **lõi lưu trữ trạng thái chung** cho rate limit, kết hợp với các instance Gateway trên Kubernetes để đảm bảo:  
  - **Tính nhất quán**: Counter rate limit được đồng bộ cho mọi request dù đến bất kỳ instance nào.  
  - **Khả năng mở rộng**: Cân bằng tải và xử lý hàng nghìn request/giây nhờ Redis Cluster + Kubernetes HPA.  
  - **Tính sẵn sàng cao**: Cơ chế fallback (local cache + Circuit Breaker) giúp hệ thống tiếp tục hoạt động khi Redis fail.  