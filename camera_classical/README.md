# Bản PC Haar/FaceMesh để đối chiếu EAR/MAR

Bản này giữ Haar cascade, MediaPipe FaceMesh và hình học EAR/MAR để quan sát trên PC. Logic cảnh báo đã chuyển sang `driver_monitor.core` qua wrapper `drowsiness.py`; không còn cửa sổ ngáp theo 16 frame. Giá trị hình học được hiển thị để đối chiếu, không ghi đè nhãn AI. Confidence mắt thấp/mất mặt giữ `UNKNOWN`.

Runtime chính dùng YuNet, hai classifier, camera/video, JSONL và các backend ONNX/RKNN: [hướng dẫn sử dụng](../README_DRIVER_MONITOR.md). Radxa dùng runtime này và không phụ thuộc MediaPipe.

Muốn chạy bản đối chiếu PC, cài dependency riêng `camera_classical/requirements.txt` trong môi trường PC thích hợp rồi:

Runtime chính dùng môi trường `.venv` tại gốc. Môi trường `.venv` cũ lồng trong thư mục này đã được dọn; chỉ cần tạo lại môi trường riêng nếu thực sự chạy bản đối chiếu.

```bat
python camera_classical\camera_classical.py --camera 0 --eye-model camera_classical\best_eye.pt --yawn-model camera_classical\best_yawn.pt
```

Model mắt thực có thứ tự `Closed, Open`, ngáp `no_yawn, yawn`; đều YOLOv8n classification. Các ngưỡng EAR/MAR chỉ là giá trị thử nghiệm cần hiệu chỉnh theo camera. Bản đối chiếu chưa được chạy end-to-end với MediaPipe trong phiên triển khai này; kiểm thử wrapper logic và bộ runtime chính được ghi trong báo cáo.

Tham số serial `--esp32-port COM7` dùng chung ACK/heartbeat/watchdog, xem [firmware](../esp32_buzzer/README.md). Bản dùng chung là lựa chọn cho thu log/nghiệm thu; file PC này dành cho đối chiếu hình học.
