Chạy chương trình thông qua file `main.py`:

```bash
python main.py "đường_dẫndẫn_đếnđến_file.md" --output_dir "result" --title "Ten_Tai_Lieu"
```

**Các tham số:**
- `input`: Đường dẫn đến file Markdown đầu vào.
- `--output_dir`: Thư mục lưu kết quả (mặc định: `result`).
- `--title`: Tiêu đề tài liệu (nếu không có sẽ lấy tên file).

## 📂 Cấu trúc đầu ra (Output Schema)

Mỗi chunk được trả về dưới dạng JSON chuẩn hóa:

```json
{
  "id": "uuid-string",
  "content": "Nội dung đoạn văn bản hoặc bảng biểu",
  "metadata": {
    "doc_title": "Tên tài liệu",
    "hierarchy": {
      "level_1": "Chương I",
      "level_2": "Mục 1",
      "level_3": "Điều 5",
      "level_4": "Khoản 2"
    },
    "extra": {
      "length": 1250,
      "type": "table" 
    }
  }
}
```
