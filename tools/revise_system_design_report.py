"""Apply the reviewed project-scope and design-figure revision to the report.

This is a one-time migration of the existing Markdown source. Keep a source
snapshot and a removal/evidence audit; never modify the user's reference files.
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/BAO_CAO_GIAM_SAT_BUON_NGU_THEO_MAU.md"
QA = ROOT / "reports/reference_style/system_design_scope"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section_span(text, number):
    matches = list(re.finditer(r"^(#{1,3}) (.+)$", text, re.MULTILINE))
    for index, match in enumerate(matches):
        if re.match(re.escape(number) + r"\.\s", match.group(2)):
            level = len(match.group(1))
            end = next((m.start() for m in matches[index+1:] if len(m.group(1)) <= level), len(text))
            return match, end
    raise ValueError(f"Section missing: {number}")


def set_section(text, number, body):
    match, end = section_span(text, number)
    return text[:match.end()] + "\n\n" + body.strip() + "\n\n" + text[end:]


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Replacement is missing or ambiguous: {old[:100]}")
    return text.replace(old, new, 1)


def main():
    original = SOURCE.read_text(encoding="utf-8")
    if "## 2.12. Tổng quan về mạch GPS định vị" not in original:
        raise ValueError("This one-time migration has already run or source differs; inspect before applying")
    QA.mkdir(parents=True, exist_ok=True)
    snapshot = QA / "source_before.md"
    if snapshot.exists():
        raise FileExistsError("Source snapshot already exists; preserve the prior audit")
    snapshot.write_text(original, encoding="utf-8")
    protected = [ROOT / "reports/BAO_CAO_GIAM_SAT_BUON_NGU_BO_SUNG_LY_THUYET.docx",
                 ROOT / "BAO_CAO_DA2_HE_THONG_GIAM_SAT_TAI_XE.docx",
                 Path(r"C:\Users\P1 Gen 5\Downloads\ung-dung-xu-ly-anh-iot-trong-giam-sat-tai-xe-tren-o-to.pdf"),
                 Path(r"C:\Users\P1 Gen 5\Downloads\ung-dung-xu-ly-anh-iot-trong-giam-sat-tai-xe-tren-o-to.docx")]
    protected_hashes = {str(p): digest(p) for p in protected if p.is_file()}
    text, removed = original, []
    for number in ("2.2", "2.3", "2.4.2", "2.6", "2.7.3", "2.11", "2.12", "2.13",
                   "3.1.3", "3.1.5", "5.1.12", "5.1.13"):
        match, end = section_span(text, number)
        removed.extend(re.findall(r"^#{1,3} (.+)$", text[match.start():end], re.MULTILINE))
        text = text[:match.start()] + text[end:]
    text = "\n".join(line for line in text.splitlines() if not line.startswith(("| EAR |", "| MAR |",
        "Trong thư mục camera_classical còn có chương trình đối chiếu"))) + "\n"
    text = replace_once(text,
        " Năm điểm mốc không cung cấp đầy đủ các điểm mí mắt cần để tính EAR theo phương pháp hình học thông thường.", "")
    text = replace_once(text,
        "Đây là kiểm tra liên tục của vùng theo dõi, chưa phải thuật toán nhận diện danh tính.",
        "Phép kiểm tra này xác định tính liên tục của vùng theo dõi bằng hình học khuôn mặt.")
    text = replace_once(text,
        "Phạm vi thực hiện gồm nhận biết biểu hiện, cảnh báo tại chỗ và lưu nhật ký. GPS, SMS, nhận diện danh tính và bảng điều khiển từ xa chưa thuộc hệ thống được triển khai. Bo Radxa và ESP32 chưa có kết quả vận hành thực tế trong hồ sơ kiểm thử của dự án.",
        "Phạm vi thực hiện gồm quan sát mắt và ngáp bằng camera, xử lý trên PC hoặc Radxa, gửi lệnh USB serial tới ESP32 để điều khiển buzzer và lưu nhật ký tại máy tính xử lý. Khối phần cứng cảnh báo chỉ gồm ESP32 và buzzer. Radxa chưa được setup; các mục đo NPU, phản ứng buzzer thật và vận hành dài hạn được để trống khi chưa có kết quả.")
    text = replace_once(text,
        "Dữ liệu hiện có chủ yếu là ảnh tĩnh và các video kỹ thuật dùng kiểm tra tích hợp.",
        "Dữ liệu hiện có gồm ảnh tĩnh, video kỹ thuật dùng kiểm tra tích hợp và một video camera được người thực hiện ghi để hiệu chỉnh nhận biết ngáp.")
    text = replace_once(text,
        "Cấu hình PC hiện tại sử dụng mô hình mắt eye_refined_v4 và mô hình ngáp smile_refined.",
        "Cấu hình PC hiện tại sử dụng checkpoint mắt eye_refined_v4 và checkpoint ngáp yawn_camera_refined; manifest của bản ngáp tham chiếu đúng các artifact mắt đang dùng.")
    text = replace_once(text,
        "Các phép đánh giá ảnh và kiểm thử phần mềm cho thấy sự cải thiện ở các trường hợp đã kiểm tra.",
        "Các phép đánh giá ảnh và kiểm thử phần mềm cho thấy sự cải thiện ở các trường hợp đã kiểm tra. Phát lại video camera có hai đợt ngáp, bản trước xác nhận 0/2 và bản hiện tại xác nhận 2/2; đoạn cười không làm tăng bộ đếm. Video một người này đã được dùng trong hiệu chỉnh nên kết quả chỉ là kiểm thử phát triển.")
    text = replace_once(text,
        "Bản kiểm tra sau hiệu chỉnh mô hình mắt ghi nhận 64 kiểm thử driver_monitor và 2 kiểm thử tương thích PC đạt yêu cầu.",
        "Bản kiểm tra sau sửa bỏ sót ngáp trên camera ghi nhận 67 kiểm thử driver_monitor đạt yêu cầu, bao gồm các ca mắt, ngáp, serial và mất dữ liệu [30].")
    text = replace_once(text,
        "Đối với model ngáp smile_refined, backbone và các khối convolution được giữ, chỉ lớp Linear 1.280→2 được huấn luyện lại.",
        "Đối với model ngáp yawn_camera_refined, backbone cùng convolution và BatchNorm của Classify được giữ; chỉ lớp Linear 1.280→2 được huấn luyện lại trên dữ liệu ảnh cũ và vùng cắt camera [30].")
    text = replace_once(text,
        "Trong cấu hình PC hiện tại, manifest mắt eye_refined_v4 tham chiếu cả mô hình mắt mới và mô hình ngáp smile_refined.",
        "Trong cấu hình PC hiện tại, manifest yawn_camera_refined quy định các artifact ngáp mới và tham chiếu nguyên trạng checkpoint mắt eye_refined_v4.")
    text = text.replace("SerialBuzzer", "SerialAlertSink")
    text = replace_once(text,
        "Tham khảo phần FaceDetectorYN và cấu trúc đầu ra phát hiện; project không sử dụng phần nhận diện danh tính của ví dụ.",
        "Tham khảo FaceDetectorYN và cấu trúc đầu ra phát hiện khuôn mặt.")
    # Add the missing design views at their corresponding implementation seams.
    additions = {
        "3.3": "Hình 3-6 phân biệt việc xác nhận hai mắt nhắm, chớp hai mắt và chu kỳ riêng từng mắt. Các nhánh dùng cùng xác suất nhưng có điều kiện thời gian khác nhau; một mắt nhắm không trở thành bằng chứng hai mắt nhắm.\n\n![Hình 3-6. Các nhánh xác nhận mắt theo thời gian](../report_assets/project_report/eye_confirmation_design.png)",
        "3.4": "Hình 3-7 trình bày ứng viên, xác nhận và kết thúc một đợt ngáp. Hai ngưỡng tạo hysteresis; chỉ thời điểm chuyển sang đợt đã xác nhận làm tăng bộ đếm.\n\n![Hình 3-7. Thiết kế xác nhận một đợt ngáp](../report_assets/project_report/yawn_confirmation_design.png)",
        "3.7": "Cấu trúc phần mềm tại Hình 3-10 thể hiện ranh giới giữa Capture, Vision/classifiers, Monitor và các khối đầu ra. Observation chứa thời điểm, chất lượng và xác suất theo tên lớp; Status chứa trạng thái, nguyên nhân và số sự kiện. SerialAlertSink tiếp nhận trạng thái bật/tắt, còn Journal ghi kết quả cùng cấu hình phiên.\n\n![Hình 3-10. Thiết kế các module của runtime dùng chung](../report_assets/project_report/software_module_design.png)"
    }
    for number, addition in additions.items():
        match, end = section_span(text, number)
        text = text[:end].rstrip() + "\n\n" + addition + "\n\n" + text[end:]
    text = replace_once(text, "Khối serial nhận trạng thái cảnh báo và nguyên nhân.",
        "Hình 3-8 tổng hợp ba bằng chứng: nhắm mắt kéo dài, ngáp thường xuyên và chớp mắt tăng. Khi mắt chưa chắc chắn, trạng thái tổng thể là UNKNOWN và buzzer tắt; kênh ngáp hợp lệ vẫn có thể được ghi nhận riêng. Nhánh hồi phục giữ cảnh báo đến khi có đủ 1 giây quan sát hợp lệ sau khi hết điều kiện kích hoạt.\n\n![Hình 3-8. Thiết kế hợp nhất bằng chứng và trạng thái cảnh báo](../report_assets/project_report/alert_decision_design.png)\n\nKhối serial nhận trạng thái cảnh báo và nguyên nhân.")
    match, end = section_span(text, "3.6")
    text = text[:end].rstrip() + "\n\nHình 3-9 mô tả lệnh, ACK, heartbeat và nhánh watchdog trong firmware. Trao đổi serial này điều khiển trực tiếp khối ESP32–buzzer; hình biểu diễn thiết kế, không phải phép đo độ trễ trên phần cứng thật.\n\n![Hình 3-9. Trao đổi lệnh ESP32 và điều khiển buzzer](../report_assets/project_report/serial_buzzer_sequence.png)\n\n" + text[end:]
    # Retain real data sources and update the active camera refinement.
    match, end = section_span(text, "4.3.2")
    text = text[:end].rstrip() + "\n\nVideo 20261007T070644_475102Z.avi có 1.131 frame, dài 37,969 giây theo timestamp ghi ảnh. Nhãn được rà soát bằng hình ảnh; khoảng chuyển tiếp chưa rõ không dùng làm nhãn học. Lần ngáp đầu cung cấp đoạn train 6–9 s và validation 10–12 s. Lần ngáp thứ hai 28–34 s chỉ được đo sau khi chốt model. Mẫu train camera lấy cách nhau ít nhất 0,2 s, có 14 vùng ngáp, 28 vùng bình thường và 10 vùng cười. Các đoạn cùng người/cùng clip vẫn có tương quan nên không được xem là test độc lập theo người [30].\n\n" + text[end:]
    text = set_section(text, "4.4.1", """
Mô hình ngáp giữ nguyên backbone, convolution và BatchNorm của Classify, chỉ cập nhật Linear 1.280→2. Giai đoạn đầu bổ sung ảnh cười tạo bản smile_refined. Khi có video camera thật, bản này bỏ sót ngáp dù nhiều vùng mặt có chất lượng đạt; dữ liệu camera được bổ sung để tạo yawn_camera_refined [14], [30]. Kiến trúc, thứ tự lớp và tiền xử lý vẫn giữ nguyên.

Script refine_yawn_camera.py trích đặc trưng bằng cùng YuNet và quy trình cắt/tiền xử lý của runtime. Loss giữ dữ liệu ngáp và ảnh cười cũ, bổ sung nhóm camera cân bằng theo hành vi. Backbone và convolution không được cập nhật từ video một người. Các ứng viên phải giữ chỉ số ngáp cùng tỷ lệ nhận nhầm cười trên validation trước khi được lựa chọn.

Bản hiện tại dùng seed 42, Adam, learning rate 0,002, trọng số loss camera 0,15, regularization 0,001 và mốc 150. Test ảnh cũ cùng lần ngáp thứ hai không tham gia lựa chọn ứng viên; kết quả được báo sau khi lưu và khóa checkpoint. PyTorch–ONNX được đối chiếu lại từ điểm ảnh, còn phép phát lại dùng toàn bộ video và timestamp nguồn. Khoảng train/validation từ cùng clip chỉ là dữ liệu phát triển, chưa chứng minh khả năng nhận biết người khác.
""")
    manifest_path = ROOT / "models/yawn_camera_refined/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    yawn_hash = manifest["classifiers"]["yawn"]["artifacts"]["torch"]["sha256"]
    eye_hash = manifest["classifiers"]["eye"]["artifacts"]["torch"]["sha256"]
    text = set_section(text, "4.4.3", f"""
@table Bảng 4-4. Các mô hình của cấu hình camera PC hiện tại
| Thành phần | Tệp hoặc manifest | Nhãn/đặc điểm |
|---|---|---|
| Detector | models/face_detection_yunet_2023mar.onnx | Mặt và năm điểm mốc; CPU |
| Manifest PC | models/yawn_camera_refined/manifest.json | Ngáp mới; tham chiếu checkpoint mắt đang dùng |
| Mắt | models/eye_refined_v4/best_eye.pt/.onnx | Closed, Open |
| Ngáp | models/yawn_camera_refined/best_yawn.pt | no_yawn, yawn |
| ONNX ngáp | models/yawn_camera_refined/best_yawn.onnx | Xuất từ đúng checkpoint ngáp hiện tại |

SHA256 manifest PC: {digest(manifest_path)}. SHA256 checkpoint mắt: {eye_hash}. SHA256 checkpoint ngáp: {yawn_hash}. Các giá trị cho phép đối chiếu đúng bản tạo kết quả. Manifest gốc và các trọng số trước hiệu chỉnh được giữ để so sánh; artifact RKNN nền không đại diện cho trọng số PC hiện tại.
""")
    text = set_section(text, "5.1.2", """
Bảng 5-2 so sánh classifier sửa nhầm cười smile_refined với classifier hiện tại yawn_camera_refined. Trên 215 ảnh qua crop runtime, bản hiện tại có F1 lớp yawn 97,12%, macro-F1 98,09% và recall tại P≥0,70 bằng 95,28% [30]. Sáu ảnh không đạt chất lượng được tính vào bỏ sót, không loại khỏi mẫu số. Các split ảnh cũ chưa có bằng chứng độc lập theo người.

@table Bảng 5-2. So sánh trước và sau bổ sung dữ liệu camera cho classifier ngáp
| Phép đo | Bản sửa cười trước | Bản camera hiện tại |
|---|---:|---:|
| F1 yawn trên 215 ảnh qua ROI mặt | 96,62% | 97,12% |
| Macro-F1 trên cùng tập ROI mặt | 97,62% | 98,09% |
| Recall yawn tại P≥0,70 | 94,34% | 95,28% |
| Macro-F1 trên 215 ảnh gốc | 99,53% | 99,53% |
| Nhầm ngáp trên 316 ảnh cười GENKI | 2/316 | 1/316 |
| Nhầm ngáp trên 172 ảnh GENKI đạt quality | 0/172 | 0/172 |
| Nhầm ngáp trên 582 ảnh cười SMILEs | 0/582 | 0/582 |

Các phép đo ảnh cười/ảnh gốc được báo từ đặc trưng của bộ trích đã đóng băng và đầu Linear đã lưu; nhóm 215 ảnh ROI được suy luận lại từ pixel bằng ONNX. “Nhầm ngáp” ở đây là P(yawn)≥0,70 trên ảnh, chưa phải sự kiện hoặc số lần bật buzzer. SMILEs gồm ảnh mặt xám cắt 64×64, nên phép đo classifier không đại diện toàn pipeline camera với điều kiện mặt tối thiểu.

Kết quả bảo toàn các phép đo ảnh cũ trong khi cải thiện trường hợp camera đã tái hiện. Nhận biết ngáp tự nhiên, cười, nói chuyện, kính và ánh sáng khác cần tiếp tục được kiểm tra trên video mới sau khi khóa model.
""")
    text = set_section(text, "5.1.3", """
Với checkpoint mắt đang dùng, kiểm tra 407 vùng ảnh thật cho đồng thuận nhãn PyTorch–ONNX 100% và sai khác xác suất tối đa khoảng 3,24×10⁻⁶ [15]. Artifact mắt được giữ nguyên trong bản sửa ngáp.

Với classifier ngáp hiện tại, phép parity suy luận lại từ pixel trên 215 ảnh test qua cùng YuNet và quality. Có 209 ảnh được suy luận và sáu ảnh UNKNOWN; trên các mẫu suy luận, hai backend đồng thuận nhãn 100%, sai khác xác suất tối đa khoảng 1,04×10⁻⁶ và macro-F1 giảm 0 điểm phần trăm. Các ảnh UNKNOWN vẫn được tính là bỏ sót trong F1 [30].

Những kết quả này xác nhận tương đương trong phạm vi dữ liệu và hai backend đã kiểm tra. Chưa suy rộng sang RKNN/NPU của trọng số hiện tại. Mỗi bước chuyển đổi tiếp theo cần cùng bộ đầu vào đối chiếu và manifest rõ ràng.
""")
    text = replace_once(text,
        "Hồ sơ eye_classifier_verification.json ghi nhận 64 kiểm thử package và 2 kiểm thử tương thích PC đạt, không có kiểm thử thất bại [15].",
        "Bộ kiểm thử hiện tại trong tests/ ghi nhận 67 kiểm thử đạt sau sửa bỏ sót ngáp, không có kiểm thử thất bại [30]. Các fixture camera thật kiểm tra ngáp, cười, trạng thái bình thường và tương đương PyTorch–ONNX. Báo cáo software_tests.json của lần rà soát lưu kết quả chạy cùng thời điểm hoàn thiện tài liệu [31].")
    text = replace_once(text,
        "Phiên thành công gần nhất được lưu tại reports/eye_classifier_camera_check/20261006T162405_044346Z.summary.json, sử dụng source 0, ONNX và profile PC [19].",
        "Phiên camera tham chiếu trước bản sửa ngáp được lưu tại reports/eye_classifier_camera_check/20261006T162405_044346Z.summary.json, sử dụng source 0 và ONNX [19].")
    text = text.replace("@table Bảng 5-4. Đối chiếu bằng chứng với các chỉ tiêu", "@table Bảng 5-5. Đối chiếu bằng chứng với các chỉ tiêu")
    # Renumber only headings, never equations/tables or numerical thresholds.
    chapter_two = {4:2, 5:3, 7:4, 8:5, 9:6, 10:7, 14:8, 15:9, 16:10, 17:11}
    def renumber(match):
        marks, number, title = match.groups()
        parts = list(map(int, number.split('.')))
        old = tuple(parts)
        if len(parts) >= 2 and parts[0] == 2 and parts[1] in chapter_two:
            parts[1] = chapter_two[parts[1]]
            if len(parts) == 3 and old[:2] == (2,4) and old[2] >= 3:
                parts[2] -= 1
            if old == (2,7,4):
                parts[2] = 3
        elif old == (3,1,4):
            parts[2] = 3
        elif len(parts) == 3 and old[:2] == (5,1) and parts[2] >= 7:
            parts[2] += 1
        return marks + " " + '.'.join(map(str, parts)) + ". " + title
    text = re.sub(r"^(#{1,3}) (\d+(?:\.\d+)*)\.\s+(.+)$", renumber, text, flags=re.MULTILINE)
    replay = """
### 5.1.7. Phát lại video camera sau hiệu chỉnh ngáp

Video 20261007T070644_475102Z.avi được phát lại qua decoder, YuNet, ba vùng cắt, các classifier và Monitor bằng ONNX. Hai bản dùng cùng 1.131 frame, cùng timestamp ghi ảnh và cùng ngưỡng chất lượng/quyết định. Nhãn sự kiện được rà soát từ hình ảnh, với hai đợt ngáp và 17 giây bình thường có nhãn, gồm đoạn cười [30].

@table Bảng 5-4. Kết quả phát lại video camera để sửa bỏ sót ngáp
| Chỉ số | Bản sửa cười trước | Bản camera hiện tại |
|---|---|---|
| Frame được xử lý | 1.131 | 1.131 |
| Thời gian nguồn | 37,969 s | 37,969 s |
| Ngáp được xác nhận | 0/2 đợt | 2/2 đợt |
| Thời điểm xác nhận | Không có | 10,625 s và 29,047 s |
| Sự kiện ngáp trong 17 s bình thường có nhãn | 0 | 0 |
| Sự kiện ngáp dư ngoài hai đợt có nhãn | 0 | 0 |

Hình 5-1 cho thấy xác suất ở hai đợt ngáp trước/sau sửa và thời điểm bộ đếm tăng. Điều kiện xác nhận vẫn là P sau EMA≥0,70 liên tục 1 giây, EMA có τ=0,20 giây. Bản mới không làm tăng bộ đếm trong đoạn cười của clip.

![Hình 5-1. Xác suất và bộ đếm ngáp trước và sau hiệu chỉnh camera](yawn_camera_check/candidate.regression.png)

Bản hiện tại xử lý offline khoảng 51,37 FPS với p95 từ đọc frame tới quyết định 33 ms theo summary. Đây là tốc độ phát lại trên PC, không phải FPS camera trực tiếp hoặc NPU Radxa. Có 373 frame bị đánh giá mờ; tổng UNKNOWN là 512/1.131 frame, tương đương 45,27%, còn gồm mắt chưa rõ và chuyển động đầu. Nhiều frame mờ làm lần ngáp đầu xác nhận muộn.

Video này đã được xem và dùng hiệu chỉnh một phần nên phép phát lại là kiểm thử phát triển. Lần ngáp thứ hai không tham gia train/chọn model nhưng vẫn cùng người/cùng clip. Không sử dụng kết quả 2/2 để tuyên bố recall độc lập hoặc 0 báo nhầm trong 17 giây để chứng minh ≤1 lần/giờ. Các mục nghiệm thu cabin độc lập và phần cứng tiếp tục để trống.

"""
    text = replace_once(text, "### 5.1.8. Kết quả chuyển đổi RKNN nền", replay.strip() + "\n\n### 5.1.8. Kết quả chuyển đổi RKNN nền")
    text = replace_once(text,
        "Hiệu chỉnh ngáp làm giảm nhận nhầm các ảnh cười trong tập giữ riêng và vẫn bảo toàn khả năng nhận biết ngáp ở phép đánh giá hiện có.",
        "Hiệu chỉnh ngáp giữ hiệu quả trên ảnh cười và bảo toàn ngáp ở tập ảnh cũ; video camera phát triển cải thiện từ 0/2 lên 2/2 đợt xác nhận. Kết quả video này đã tham gia hiệu chỉnh nên chưa phải nghiệm thu độc lập.")
    text = text.rstrip() + "\n\n[30] Hồ sơ dự án, reports/YAWN_CAMERA_FIX.md; models/yawn_camera_refined/manifest.json; validation.json; evaluation.json; reports/yawn_camera_check/candidate.regression.json; yawn_onnx_parity.json; tools/refine_yawn_camera.py; tools/check_yawn_replay.py; tests/test_yawn_camera_classifier.py. Bản sửa ngáp và video camera phát triển ngày 07/10/2026.\n\n[31] Hồ sơ rà soát báo cáo, reports/reference_style/system_design_scope/scope_audit.json; software_tests.json. Đối chiếu phạm vi với driver_monitor/, cấu hình camera_pc.yaml và esp32_buzzer/esp32_buzzer.ino.\n"
    forbidden = r"\b(?:GPS|SIM800L|GSM|GPRS|SMS|cvzone|FaceNet|AdaBoost|Haar(?:-like)?|EAR|MAR|MQTT|Firebase)\b|giọng nói|danh tính|website|bảng điều khiển từ xa"
    if re.search(forbidden, text, re.IGNORECASE):
        raise ValueError("Out-of-scope content remains: " + re.search(forbidden, text, re.IGNORECASE).group())
    if text.count("![Hình 3-") != 10:
        raise ValueError("Unexpected Chapter 3 figure count")
    SOURCE.write_text(text, encoding="utf-8")
    audit = {"source": str(SOURCE), "source_before_sha256": digest(snapshot), "source_after_sha256": digest(SOURCE),
             "removed_headings": removed, "removed_topics": ["GPS/SIM800L/SMS", "remote website", "driver identity", "AdaBoost/Haar/cvzone/FaceNet", "EAR/MAR from the comparison pipeline"],
             "active_manifest": str(manifest_path), "active_manifest_sha256": digest(manifest_path),
             "hardware_scope": "Camera -> PC/Radxa -> USB serial -> ESP32 -> buzzer; local logs/display",
             "added_design_figures": ["eye_confirmation_design", "yawn_confirmation_design", "alert_decision_design", "serial_buzzer_sequence", "software_module_design"],
             "total_figures": len(re.findall(r"^!\[", text, re.MULTILINE)),
             "protected_sources": protected_hashes, "unmeasured_in_scope_sections": "Headings retained with empty content"}
    (QA / "scope_audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"removed_headings": len(removed), "added_design_figures": 5, "total_figures": audit["total_figures"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
