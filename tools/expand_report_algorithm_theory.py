"""Expand the existing report with theory grounded in the current runtime."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'reports/BAO_CAO_GIAM_SAT_BUON_NGU_THEO_MAU.md'


def main():
    text = SOURCE.read_text(encoding='utf-8')
    if '### 2.14.4. Nguyên lý mạng nơ-ron tích chập' in text:
        raise SystemExit('Theory expansion already applied.')
    for number in range(1, 6):
        text = text.replace(f'(2.{number})', f'{{EQ:old{number}}}')

    def insert_before(anchor, content):
        nonlocal text
        if text.count(anchor) != 1:
            raise ValueError('Missing or duplicate anchor: ' + anchor)
        text = text.replace(anchor, content.strip() + '\n\n' + anchor)

    insert_before('## 2.2. Giải thuật AdaBoost', '''
Để mô tả độ sắc nét, gọi G là ảnh mức xám và L là kết quả áp dụng Laplace. Toán tử này phản ánh biến thiên bậc hai theo hai hướng của ảnh [21]. Trong chương trình, phương sai của L được dùng làm chỉ số sắc nét S; μ là giá trị trung bình của L và N là số điểm ảnh.

@equation L = ∂²G/∂x² + ∂²G/∂y²;    S = (1/N)Σ(L − μ)²             {EQ:laplace}

Khi các chi tiết cạnh bị làm mờ, đáp ứng Laplace thường giảm. Tuy nhiên, nhiễu và họa tiết nền cũng có thể làm phương sai tăng. Vì vậy, S là chỉ báo chất lượng theo cấu hình camera, không phải một chứng nhận rằng mí mắt đã được quan sát đúng. Mã nguồn tính chỉ số trên cả mặt và từng ROI mắt; một vùng mặt rõ không thay thế điều kiện hai vùng mắt rõ.

Độ sáng được biểu diễn bằng median(G), giúp giảm ảnh hưởng của một số điểm ảnh có giá trị cực đoan. Tỷ lệ quá sáng được tính bằng số điểm ảnh G>235 chia cho N. Nếu chỉ số trên mặt hoặc mắt không đạt điều kiện, quan sát bị loại khỏi xác nhận liên tục. Các ngưỡng được trình bày ở Chương 3 là lựa chọn phát triển của project, cần kiểm chứng bằng dữ liệu cabin.

### 2.1.5. Nội suy và chuẩn hóa đầu vào

Thay đổi kích thước ảnh cần xác định giá trị tại các vị trí không trùng với lưới điểm ảnh cũ. Nội suy bilinear sử dụng bốn điểm lân cận và trọng số theo khoảng cách theo hai hướng. Với a và b thuộc [0,1] là phần tọa độ nằm giữa các điểm lưới, giá trị nội suy được biểu diễn như sau.

@equation I = (1−a)(1−b)I₀₀ + a(1−b)I₁₀ + (1−a)bI₀₁ + abI₁₁     {EQ:bilinear}

Chương trình classifier dùng PIL bilinear, đổi BGR thành RGB rồi đưa cạnh ngắn về 224 pixel. Cạnh còn lại được tính theo tỷ lệ, sau đó cắt giữa thành 224×224. Quy trình này giữ tỷ lệ trước khi cắt; một phần ngoài rìa ROI có thể bị bỏ. Việc kéo trực tiếp mọi vùng ảnh thành hình vuông có thể thay đổi hình học đầu vào so với quy trình đã dùng để huấn luyện và đánh giá.

Giá trị điểm ảnh uint8 được chuyển sang số thực, chia cho 255 và chuẩn hóa theo mean, std trong manifest. Với cấu hình hiện có, mean bằng 0 và std bằng 1 nên bước chuẩn hóa chỉ đưa giá trị về [0,1]. Đây là chuẩn hóa dữ liệu đầu vào, khác với Batch Normalization bên trong mạng. Backend RKNN nhận uint8 và sử dụng cấu hình chuyển đổi tương ứng; chia 255 ở cả host lẫn graph sẽ làm sai đầu vào.
''')

    insert_before('## 2.5. Khoảng cách Euclid', '''
### 2.4.4. Nguyên lý phát hiện khuôn mặt bằng YuNet

YuNet là bộ phát hiện khuôn mặt dùng mạng nơ-ron được cung cấp qua OpenCV Zoo [1]. Hệ thống gọi FaceDetectorYN với model ONNX để nhận vị trí mặt và năm điểm mốc. Mỗi hàng kết quả chứa tọa độ hộp mặt, tọa độ hai mắt, mũi, hai vị trí miệng và điểm tin cậy. Các thông tin đầu ra này được mô tả trong ví dụ chính thức của OpenCV [22].

Trong chuỗi xử lý, mạng tạo ứng viên khuôn mặt từ đặc trưng của ảnh. Bộ tiếp nhận lọc ứng viên theo điểm tin cậy và áp dụng loại bỏ cực đại không trùng, hay NMS, để giảm các hộp cùng mô tả một khuôn mặt. Mã nguồn project đặt ngưỡng điểm tin cậy 0,80, ngưỡng NMS 0,30 và top-k bằng 5.000. Top-k là giới hạn ứng viên trước NMS, không phải số tài xế được theo dõi.

Sau khi phát hiện, runtime tiếp tục lọc theo tâm mặt nằm trong ROI ghế lái và kích thước mặt tối thiểu. Chỉ trường hợp còn đúng một mặt mới được xử lý. Không có mặt tạo no_face; nhiều mặt phù hợp tạo ambiguous_faces. Bộ phát hiện trả vị trí, còn hai classifier trả biểu hiện mắt và ngáp. Năm điểm mốc không cung cấp đầy đủ các điểm mí mắt cần để tính EAR theo phương pháp hình học thông thường.

### 2.4.5. IoU và loại bỏ các hộp trùng

Intersection over Union, viết tắt IoU, là tỷ số diện tích phần giao với diện tích phần hợp của hai hộp A và B. Giá trị nằm trong [0,1]; giá trị lớn biểu thị hai hộp chồng lấp nhiều.

@equation IoU(A,B) = |A ∩ B| / |A ∪ B|                              {EQ:iou}

NMS xét các hộp theo thứ tự điểm tin cậy, giữ hộp có điểm cao rồi loại các hộp có mức chồng lấp vượt ngưỡng. Quá trình lặp lại với các hộp còn lại. Trong project, NMS do FaceDetectorYN thực hiện. Hàm iou trong vision.py có nhiệm vụ riêng: so sánh hộp mặt mở rộng hiện tại với hộp trước đó để nhận biết sự thay đổi đối tượng theo dõi khi IoU nhỏ hơn 0,20.

Điều kiện đổi đối tượng làm xóa lịch sử sự kiện nhằm tránh ghép dữ liệu của các khuôn mặt khác nhau. Đây là kiểm tra liên tục của vùng theo dõi, chưa phải thuật toán nhận diện danh tính. Một chuyển động lớn cũng có thể làm hộp thay đổi đủ nhiều để xóa lịch sử; giới hạn này cần được xem xét khi đánh giá camera thực.

### 2.4.6. Letterbox và chuyển ngược tọa độ

Letterbox thu nhỏ ảnh theo một hệ số chung rồi thêm vùng đệm để đạt kích thước yêu cầu. Với ảnh gốc W×H và kích thước detector D×D, hệ số tỷ lệ r được chọn theo cạnh giới hạn. Gọi oₓ, oᵧ là độ lệch vùng đệm; điểm phát hiện (x′,y′) được đưa về ảnh gốc theo công thức sau.

@equation r = min(D/W,D/H);    x = (x′−oₓ)/r;    y = (y′−oᵧ)/r      {EQ:letterbox}

Runtime dùng D=320, làm tròn kích thước ảnh thu nhỏ và chia vùng đệm về hai phía. Ví dụ ảnh 640×480 có hệ số 0,5, tạo vùng ảnh 320×240 với đệm theo chiều cao. Cả hộp mặt và năm điểm mốc đều phải bỏ độ lệch này trước khi chia tỷ lệ. ROI được cắt trên ảnh gốc, không cắt từ ảnh detector đã thu nhỏ.
''')

    insert_before('## 2.15. Quyết định theo thời gian', '''
### 2.14.4. Nguyên lý mạng nơ-ron tích chập

Mạng nơ-ron tích chập, viết tắt CNN, học các phép biến đổi trên vùng lân cận của ảnh để tạo bản đồ đặc trưng. Một lớp tích chập sử dụng các bộ lọc có trọng số dùng chung ở nhiều vị trí. Các lớp được ghép liên tiếp, tạo biểu diễn được dùng bởi lớp phân loại. Trong đề tài, mạng học đặc trưng từ ảnh mắt hoặc mặt thay cho việc lập trình một ngưỡng độ sáng cố định để nhận biết biểu hiện.

Phép tích chập trong cách triển khai Conv2d của PyTorch được tính bằng tương quan chéo giữa đầu vào và bộ lọc [23]. Bỏ qua chi tiết padding để trình bày nguyên lý, với X là đầu vào, K là bộ lọc và b là bias, phần tử đầu ra có thể viết như sau.

@equation Yₒ(i,j) = bₒ + Σc Σu Σv Kₒ,c(u,v)Xc(i·s+u,j·s+v)        {EQ:conv}

Các ký hiệu o và c biểu thị kênh đầu ra và đầu vào; u,v là chỉ số trong bộ lọc; s là stride. Bộ lọc 3×3 sử dụng một vùng lân cận để tạo đặc trưng, còn stride 2 giảm số vị trí đầu ra. Padding bổ sung biên để kiểm soát kích thước. Bộ lọc 1×1 biến đổi các kênh tại cùng một vị trí, không mở rộng trực tiếp vùng lân cận không gian.

Trong lớp Conv của Ultralytics được cài trong project, phép Conv2d nối với BatchNorm2d và SiLU. Batch Normalization chuẩn hóa theo thống kê kênh rồi áp dụng hai hệ số học được γ và β [24]. Trong huấn luyện, thống kê được tính từ dữ liệu của batch; khi đánh giá, lớp dùng thống kê lưu trong model.

@equation BN(x) = γ(x−μ)/√(σ²+ε) + β                                {EQ:bn}

SiLU là hàm kích hoạt kết hợp đầu vào với sigmoid [25]. Nó tạo quan hệ phi tuyến để một chuỗi lớp không bị rút gọn thành một phép biến đổi tuyến tính duy nhất.

@equation SiLU(x) = x·sigmoid(x) = x/(1+exp(−x))                     {EQ:silu}

Các phép tính trên mô tả cấu trúc mạng đã kiểm kê. Chúng không bảo đảm rằng classifier sẽ nhận đúng mọi góc mặt, kính hoặc điều kiện ánh sáng. Hiệu quả của trọng số cần được kiểm tra trên đầu vào tạo bằng pipeline camera, vì sự khác nhau giữa crop huấn luyện và crop vận hành có thể thay đổi kết quả.

### 2.14.5. Khối C2f và đầu phân loại

Theo mã nguồn C2f trong thư viện Ultralytics của môi trường project, đầu vào đi qua Conv 1×1 rồi được chia thành hai phần theo kênh. Một phần được giữ, phần còn lại đi qua chuỗi bottleneck. Đầu ra mỗi bottleneck cũng được giữ để ghép với các phần trước. Sau phép ghép, Conv 1×1 tạo số kênh đầu ra yêu cầu. Trình tự này tương ứng với Hình 2-2 và mô tả chính thức của khối C2f [26].

Có thể biểu diễn nguyên lý bằng các tensor A, B₀ sau phép chia; Bᵢ là đầu ra bottleneck thứ i và n là số bottleneck. Phép Concat ghép tensor theo chiều kênh, không cộng giá trị từng phần tử.

@equation Bᵢ = Fᵢ(Bᵢ₋₁);    Y = Conv₁×₁(Concat(A,B₀,…,Bₙ))         {EQ:c2f}

Bottleneck trong khối sử dụng hai phép Conv 3×3. Nếu shortcut được bật và kích thước phù hợp, đầu vào được cộng vào đầu ra đã biến đổi, tạo kết nối dư Y=X+F(X). Phép cộng này yêu cầu cùng kích thước tensor. Cấu hình số bottleneck trong các tầng của checkpoint nano là 1, 2, 2 và 1 như Bảng 2-1; không áp dụng thông số của một model detector khác cho hai classifier này.

Đầu Classify biến đổi tensor cuối backbone thành 1.280 kênh rồi dùng gộp trung bình toàn cục, hay GAP. Mỗi kênh được lấy trung bình theo hai chiều không gian để tạo một phần tử vector đặc trưng. Với U là tensor trước GAP, đặc trưng f ở kênh k có dạng sau [27].

@equation fₖ = (1/(H·W))Σi Σj Uₖ(i,j);    z = Wf + b                {EQ:gap}

Lớp tuyến tính biến vector f thành hai điểm số z, sau đó Softmax tạo xác suất khi suy luận. Với bộ ngáp, hai điểm số tương ứng no_yawn và yawn; với bộ mắt, chúng tương ứng Closed và Open. Toàn vùng ảnh đầu vào được tổng hợp thành một nhãn phân loại, vì vậy đầu Classify không tạo hộp định vị mắt hoặc miệng.

### 2.14.6. Hàm mất mát và học chuyển giao

Huấn luyện có giám sát sử dụng ảnh cùng nhãn để điều chỉnh trọng số, sao cho mô hình tăng điểm số cho lớp đúng. Cross-entropy đo sai khác giữa phân phối dự đoán và nhãn. Với yᵢ,c bằng 1 khi ảnh i thuộc lớp c và bằng 0 ở lớp còn lại, mất mát trung bình được biểu diễn dưới đây [28].

@equation LCE = −(1/N)Σi Σc yᵢ,c·log(pᵢ,c)                          {EQ:ce}

Các script hiệu chỉnh trong project gọi cross_entropy trên logits; hàm thực hiện phần chuyển điểm số sang dạng log xác suất. Đầu ra Softmax dùng cho suy luận không được đưa qua Softmax thêm một lần trước hàm này. Các mẫu có trọng số theo nhóm nguồn và lớp để một nhóm dữ liệu lớn không chi phối toàn bộ mất mát. Giá trị mất mát và chỉ số validation phục vụ lựa chọn model, còn test được giữ cho đánh giá sau khi chốt.

Học chuyển giao tận dụng một phần trọng số đã có, rồi cập nhật phần cần thích nghi với dữ liệu mới. Đối với model ngáp smile_refined, backbone và các khối convolution được giữ, chỉ lớp Linear 1.280→2 được huấn luyện lại. Với model mắt hiệu chỉnh ở profile PC, script refine_eye_tail.py cập nhật phần cuối Classify trên các đặc trưng backbone đã trích, gồm khối Conv và Linear. Cách chọn phần huấn luyện được xác định từ script và so sánh checkpoint, không suy ra chỉ từ tên file [14], [15].

Script huấn luyện lại lớp Linear dùng Adam; script hiệu chỉnh phần cuối model mắt dùng AdamW. Các bộ tối ưu theo dõi trung bình động của gradient và bình phương gradient để điều chỉnh bước cập nhật từng tham số. AdamW còn áp dụng weight decay tách khỏi cập nhật gradient. Các thuật toán này chỉ chạy trong giai đoạn huấn luyện; khi camera hoạt động, runtime suy luận với trọng số đã chốt và không tự học thêm từ tài xế.

Mẫu cười, nói chuyện hoặc mắt mở ở góc khó có thể cung cấp dữ liệu âm quan trọng. Tuy nhiên, nếu một ảnh lỗi đã được đưa vào train thì kết quả đúng trên chính ảnh đó chỉ là kiểm tra hồi quy. Tính tổng quát cần được đo trên ảnh và video chưa dùng để huấn luyện, ưu tiên tách theo người để hạn chế rò rỉ.
''')

    insert_before('## 2.16. Các chỉ số đánh giá', '''
### 2.15.1. Quan sát hợp lệ và tính liên tục của thời gian

Thuật toán theo thời gian tiếp nhận Observation gồm timestamp, phân phối xác suất từng mắt, phân phối ngáp và chỉ số chất lượng. Điều kiện hợp lệ bao gồm đúng nhãn, giá trị hữu hạn, từng xác suất thuộc [0,1] và tổng gần bằng 1 trong sai số 0,001. Timestamp phải tăng nghiêm ngặt; timestamp đảo hoặc lặp bị từ chối. Tuổi frame và khoảng cách giữa các frame được kiểm tra để tránh dùng ảnh cũ như bằng chứng mới.

Với chuỗi quan sát đang xét, Δt=tₖ−tₖ₋₁ là khoảng cách thời gian. Khoảng vượt 0,25 s ngắt xác nhận. Một chuỗi đủ 1,5 s không chỉ có điểm đầu và điểm cuối cách nhau 1,5 s; mọi quan sát trung gian phải thỏa điều kiện duy trì. Ví dụ nhắm ở t=0 rồi mất camera đến t=2 không được kết luận đã nhắm liên tục hai giây.

Camera sử dụng đồng hồ monotonic, trong khi video sử dụng thời gian nguồn hoặc sidecar timestamp. Do đó, xử lý clip nhanh hơn tốc độ thực không làm các thời gian xác nhận bị rút ngắn. Đây là cơ sở để cùng một logic được dùng khi chạy trực tiếp và khi phát lại dữ liệu kiểm thử.

### 2.15.2. Phân loại từng mắt và xác nhận nhắm kéo dài

Gọi p₁ và p₂ là xác suất Closed của hai ROI mắt. Mỗi mắt được coi Closed khi p≥0,80; Open khi 1−p≥0,80; ngoài hai miền đó là chưa xác định. Hai miền quyết định tách nhau nên một xác suất nằm gần ranh giới không bị ép thành nhãn chắc chắn.

@equation C = (p₁≥0,80) ∧ (p₂≥0,80);    O = (p₁≤0,20) ∧ (p₂≤0,20)   {EQ:eyes}

Khi C đúng trên các quan sát liên tiếp hợp lệ, thuật toán ghi t₀ tại lần đầu và tính T=t−t₀. T đạt 1,5 s tạo bằng chứng nhắm mắt kéo dài. Một mắt nhắm và một mắt mở không thỏa C, do đó không tạo nhánh cảnh báo này. Nếu chất lượng hoặc độ chắc chắn không đạt, chuỗi xác nhận nhắm kéo dài bị xóa và hệ thống trả UNKNOWN.

Mức confidence là một điều kiện của quyết định, không phải xác suất đã hiệu chuẩn rằng một người đang buồn ngủ. Nếu classifier nhận nhầm mắt mở thành Closed với p gần 1, logic vẫn có thể nhận bằng chứng sai. Ngăn lỗi này cần cải thiện dữ liệu, model hoặc chất lượng quan sát; chỉ tăng thời gian xác nhận có thể làm giảm một số báo nhầm nhưng cũng tăng độ trễ.

### 2.15.3. Đếm chu kỳ mắt và ghép chớp mắt hai mắt

Mỗi mắt có một bộ trạng thái theo dõi mở, đóng và trở lại mở. Trước khi bắt đầu hoặc hoàn tất chu kỳ, profile PC yêu cầu Open được duy trì 0,10 s. Khi đóng bắt đầu ở a và mở trở lại lần đầu ở b, thời lượng đóng là b−a; thời gian chờ xác nhận mở sau b không được cộng vào khoảng đóng.

Chu kỳ riêng một mắt được lưu làm thông tin chẩn đoán nếu thời lượng đạt tối thiểu 0,05 s. Để được dùng như blink hai mắt, mỗi chu kỳ còn phải không quá 0,50 s và có phần chồng lấp với chu kỳ mắt còn lại. Với hai khoảng đóng [a₁,b₁] và [a₂,b₂], độ dài chồng lấp được xác định như sau.

@equation Tlap = min(b₁,b₂) − max(a₁,a₂);    Tlap ≥ 0,05 s             {EQ:overlap}

Runtime ghép hai sự kiện một lần rồi loại chúng khỏi hàng đợi chờ. Chỉ hai chu kỳ ngắn phù hợp mới tăng bộ blink both; nháy riêng một mắt hoặc nhắm kéo dài chỉ có thể tăng số chu kỳ chẩn đoán. Điểm khởi tạo ở trạng thái Closed cũng chưa đủ tạo chu kỳ, vì chưa quan sát được bước mở trước đó.

Một chuyển tiếp có confidence chưa rõ được phép tồn tại trong khoảng grace tối đa 0,15 s ở bộ sự kiện mắt; nếu kéo dài hơn, chu kỳ bị ngắt. Khoảng grace này không được dùng để nối qua frame thiếu, frame cũ hoặc chất lượng không đạt. Logic nhắm kéo dài vẫn yêu cầu bằng chứng chắc chắn liên tục, khác với cơ chế xử lý chuyển tiếp ngắn của bộ đếm.

Để đánh giá chớp mắt tăng, gọi B₀ là số blink trong cửa sổ hiện tại dài 5 s và B₁ là số trong cửa sổ 5 s trước. Hai cửa sổ cần có quan sát đủ trước khi so sánh; bộ baseline chỉ sẵn sàng sau ít nhất 10 s theo dõi sự kiện mắt liên tục.

@equation BlinkIncrease = BaselineReady ∧ (B₀≥4) ∧ (B₀≥B₁+1)         {EQ:blink}

Các giá trị 4 và 1 là ngưỡng thực nghiệm của project, chưa phải một quy luật sinh lý áp dụng cho mọi người. Mất quan sát ngắt tính liên tục của baseline. Cách dùng cửa sổ theo giây giúp tránh biến thay đổi FPS thành thay đổi giả của tần suất chớp mắt.

### 2.15.4. Bộ lọc EMA theo thời gian

EMA, hay trung bình trượt hàm mũ, cập nhật giá trị đã lọc bằng cách kết hợp giá trị cũ với quan sát mới. Công thức đã trình bày dùng α phụ thuộc Δt và τ. Khi Δt nhỏ, mỗi mẫu mới có trọng số nhỏ; khi Δt lớn hơn trong miền dữ liệu hợp lệ, trọng số mẫu mới tăng. Cách này giữ cùng hằng số thời gian khi FPS thay đổi.

Với τ=0,20 s và Δt khoảng 1/15 s, α xấp xỉ 0,283. Nếu xác suất cũ bằng 0,40 và mẫu mới bằng 0,90 thì giá trị sau một bước xấp xỉ 0,542. Đó là ví dụ tính toán của bộ lọc, không phải kết quả đo trên video. Một mẫu tăng cao đơn lẻ chưa làm xác suất lọc chuyển ngay thành giá trị cao của mẫu đó.

Làm trơn tạo đánh đổi giữa dao động và độ trễ. Nó không thêm thông tin phân biệt cười với ngáp. Nếu model nhận nhầm cười liên tục, EMA có thể làm dự đoán sai ổn định hơn. Vì vậy, project lưu cả xác suất thô và xác suất lọc để đối chiếu, đồng thời hiệu chỉnh classifier bằng dữ liệu âm. Khi ngắt dữ liệu toàn frame, trạng thái lọc được xóa.

### 2.15.5. Hysteresis và xác nhận một đợt ngáp

Hysteresis dùng ngưỡng bắt đầu cao hơn ngưỡng kết thúc và duy trì trạng thái trong miền giữa. Project kết hợp nguyên lý này với bộ đếm thời gian. Ở trạng thái chưa ngáp, p đã lọc cần đạt ít nhất 0,70 liên tục 1 s để xác nhận. Khi đã ngáp, p phải giảm xuống không quá 0,35 liên tục 0,5 s để kết thúc.

Nếu xác suất ở giữa 0,35 và 0,70, một đợt đã xác nhận được giữ hoạt động nhưng một đợt mới chưa được xác nhận. Nếu điều kiện bắt đầu bị phá trước đủ 1 s, bộ đếm thời gian bắt đầu bị xóa. Tương tự, p tăng khỏi miền kết thúc trước đủ 0,5 s sẽ xóa bộ đếm kết thúc. Nhờ đó, dao động bên trong một biểu hiện không tự tạo thêm một sự kiện ở mỗi frame.

Khi chuyển sang đợt xác nhận, timestamp được thêm một lần vào hàng đợi ngáp. Các timestamp quá 60 s được loại. Gọi Y là số sự kiện còn lại, bằng chứng ngáp thường xuyên là Y≥2. Giới hạn này là quy tắc vận hành đã chọn; một sự kiện ngáp đơn lẻ được ghi nhật ký nhưng không đủ bật còi.

Khi kênh mắt chưa xác định nhưng ảnh và kênh ngáp vẫn hợp lệ, core.py tiếp tục cập nhật bằng chứng ngáp, trong khi trạng thái tổng thể vẫn UNKNOWN và còi tắt. Nếu lỗi thuộc toàn frame thì xác nhận đang dở của cả hai kênh bị ngắt. Sự kiện đã xác nhận trước đó được giữ đến khi hết cửa sổ hoặc thay đổi đối tượng; chương trình không ghép chuỗi xác nhận dở qua khoảng thiếu dữ liệu.

### 2.15.6. Máy trạng thái và hợp nhất bằng chứng

Máy trạng thái hữu hạn tổ chức quyết định theo một tập trạng thái và điều kiện chuyển. Hệ thống có NORMAL, WARNING, ALERT và UNKNOWN. Gọi E là nhắm kéo dài, F là ngáp thường xuyên và B là chớp mắt tăng; khi quan sát hợp lệ, điều kiện khởi phát ALERT được biểu diễn như sau.

@equation AlertTrigger = E ∨ (F ∧ B);    WarningEvidence = F ∨ B      {EQ:fusion}

Khi AlertTrigger đúng, bộ trạng thái bật cảnh báo và lưu nguyên nhân. Khi chỉ một bằng chứng F hoặc B xuất hiện, trạng thái là WARNING và còi chưa bật. Khi không còn điều kiện khởi phát sau một ALERT, hệ thống yêu cầu 1 s quan sát hợp lệ để hồi phục. Dữ liệu UNKNOWN làm tắt cảnh báo ngay, không chờ thời gian hồi phục.

Phép hợp nhất trên là quy tắc xác định trong chương trình, chưa phải một model học được mức buồn ngủ hoặc một thang điểm lâm sàng. Nó biểu diễn các chỉ báo hành vi đã chọn. Các tiêu chí phát hiện sự kiện và báo nhầm cần được đánh giá trên video có nhãn, tách khỏi F1 phân loại một ảnh mắt hoặc mặt.

### 2.15.7. Kiểm tra ổn định hình học khi đầu chuyển động

Bộ EyeMotion dùng đường nối hai mắt và mũi để theo dõi biến đổi hai chiều. Gọi M là trung điểm hai mắt, N là vị trí mũi và d là khoảng cách mắt; chương trình dùng tâm C=(M+N)/2, góc đường mắt θ và vị trí mũi chuẩn hóa q=(N−M)/d. Chỉ số dịch tâm giữa hai pose được chuẩn hóa bằng khoảng cách mắt trung bình.

@equation Shift = ‖Cₜ−Cᵣ‖ / ((dₜ+dᵣ)/2);    θ = atan2(Δy,Δx)      {EQ:motion}

Ngoài Shift, thuật toán kiểm tra thay đổi q, thay đổi d theo tỷ lệ và chênh lệch góc đường mắt. Pose hiện tại được so với các pose còn trong cửa sổ 0,30 s; giá trị biến đổi lớn nhất được dùng để quyết định. Cách so với cửa sổ có thể phát hiện một thay đổi diễn ra qua nhiều frame, thay vì chỉ xét hai frame kề nhau.

Biến đổi dịch tâm, hình học hoặc tỷ lệ đạt 0,08, hoặc góc thay đổi đạt 3°, làm kênh mắt thành head_motion. Chuỗi sự kiện mắt bị ngắt và chỉ được dùng trở lại sau thời gian ổn định 0,35 s. Pose cũ được bỏ sau khi phát hiện thay đổi để một tư thế mới giữ yên không bị so mãi với tư thế trước.

Các phép tính dùng năm điểm mốc, không tái tạo góc pitch/yaw ba chiều hoặc đo độ mở mí mắt. Một chuyển động nhẹ chưa qua ngưỡng vẫn có thể làm ROI thay đổi; một chớp mắt thực xuất hiện trong thời gian tạm dừng có thể bị bỏ sót. Vì vậy, bộ lọc hình học cần được đánh giá cùng classifier và logic thời gian, không chỉ quan sát việc bộ đếm giảm.
''')

    references = '''

[21] OpenCV, Laplace Operator: https://docs.opencv.org/4.x/d5/db5/tutorial_laplace_operator.html. Cơ sở toán tử Laplace; cách dùng phương sai và các ngưỡng thuộc mã nguồn project. Truy cập ngày 07/10/2026.

[22] OpenCV, DNN-based Face Detection and Recognition: https://docs.opencv.org/4.x/d0/dd4/tutorial_dnn_face.html. Tham khảo phần FaceDetectorYN và cấu trúc đầu ra phát hiện; project không sử dụng phần nhận diện danh tính của ví dụ. Truy cập ngày 07/10/2026.

[23] PyTorch, Conv2d: https://docs.pytorch.org/docs/stable/generated/torch.nn.Conv2d.html. Đối chiếu nguyên lý với nn.Conv2d trong môi trường project. Truy cập ngày 07/10/2026.

[24] PyTorch, BatchNorm2d: https://docs.pytorch.org/docs/stable/generated/torch.nn.BatchNorm2d.html. Truy cập ngày 07/10/2026.

[25] PyTorch, SiLU: https://docs.pytorch.org/docs/stable/generated/torch.nn.SiLU.html. Truy cập ngày 07/10/2026.

[26] Ultralytics, C2f và Bottleneck, nn.modules.block: https://docs.ultralytics.com/reference/nn/modules/block/. Đối chiếu mã nguồn cài trong project, Ultralytics 8.4.163. Truy cập ngày 07/10/2026.

[27] Ultralytics, Classify, nn.modules.head: https://docs.ultralytics.com/reference/nn/modules/head/. Đối chiếu cấu trúc checkpoint và mã nguồn project. Truy cập ngày 07/10/2026.

[28] PyTorch, CrossEntropyLoss: https://docs.pytorch.org/docs/stable/generated/torch.nn.CrossEntropyLoss.html. Truy cập ngày 07/10/2026.

[29] Hồ sơ dự án, driver_monitor/core.py; driver_monitor/vision.py; driver_monitor/eye_events.py; driver_monitor/eye_motion.py; driver_monitor/models.py; tools/refine_yawn_head.py; tools/refine_eye_tail.py. Cơ sở thuật toán, ngưỡng và cách hiệu chỉnh được mô tả trong báo cáo.
'''
    text += references
    text = text.replace('## 2.15. Quyết định theo thời gian\n', '## 2.15. Quyết định theo thời gian\n\nCác giải thuật tại mục này được mô tả từ core.py, eye_events.py và eye_motion.py của project [29]. Chúng xử lý các chỉ báo hành vi theo quy tắc đã chọn; kết quả nghiệm thu cần được đo bằng dữ liệu độc lập.\n')
    keys = re.findall(r'^@equation .*\{EQ:([^}]+)\}', text, re.M)
    if len(keys) != len(set(keys)):
        raise ValueError('Duplicate equation identifiers.')
    for number, key in enumerate(keys, 1):
        text = text.replace('{EQ:'+key+'}', f'(2.{number})')
    if '{EQ:' in text:
        raise ValueError('Unresolved equation reference.')
    SOURCE.write_text(text, encoding='utf-8')
    print('Expanded theory:', len(keys), 'equations;', len(text.split()), 'words total.')


if __name__ == '__main__':
    main()
