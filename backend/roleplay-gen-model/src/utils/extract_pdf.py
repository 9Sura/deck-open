from pathlib import Path
from PyPDF2 import PdfReader
import re

RAW_DIR = Path("backend/roleplay-gen-model/data/raw /BLTDM/association")
PROCESSED_DIR = Path("backend/roleplay-gen-model/data/processed/BLTDM/association")


# ----------------------------
# 🧹 Clean text
# ----------------------------
def clean_text(text: str) -> str:
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# ----------------------------
# 📄 Extract first N pages
# ----------------------------
def extract_first_pages(pdf_path: Path, num_pages: int = 2) -> str:
    try:
        reader = PdfReader(str(pdf_path))
        text = ""

        for i in range(min(num_pages, len(reader.pages))):
            page_text = reader.pages[i].extract_text()

            if page_text:
                text += f"\n--- PAGE {i+1} ---\n{page_text}"

        return clean_text(text)

    except Exception as e:
        print(f"❌ Error reading {pdf_path}: {e}")
        return ""


# ----------------------------
# 💾 Process one file
# ----------------------------
def process_file(pdf_path: Path):
    try:
        relative_path = pdf_path.relative_to(RAW_DIR)
        output_path = (PROCESSED_DIR / relative_path).with_suffix(".txt")

        if output_path.exists():
            print(f"⏭️ Skipping: {output_path.name}")
            return

        output_path.parent.mkdir(parents=True, exist_ok=True)

        text = extract_first_pages(pdf_path)

        if not text:
            print(f"⚠️ No text extracted: {pdf_path.name}")
            return

        output_path.write_text(text, encoding="utf-8")

        print(f"✅ Processed: {pdf_path.name}")

    except Exception as e:
        print(f"❌ Failed processing {pdf_path}: {e}")


# ----------------------------
# 🚀 Process ALL PDFs
# ----------------------------
def process_all():
    if not RAW_DIR.exists():
        print(f"❌ RAW_DIR not found: {RAW_DIR}")
        return

    pdf_files = list(RAW_DIR.rglob("*.pdf"))

    if not pdf_files:
        print("❌ No PDFs found.")
        return

    print(f"📂 Found {len(pdf_files)} PDFs\n")

    for pdf_path in sorted(pdf_files):
        process_file(pdf_path)

    print("\n🎉 Done processing all PDFs!")


if __name__ == "__main__":
    process_all()