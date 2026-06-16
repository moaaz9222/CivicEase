import os
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# إعداد المسارات
CHROMA_PATH = "chroma_db"
DATA_PATH = "data/raw"  # مسار مجلد البيانات الخاص بك


def build_vector_db():
    """
    تقوم هذه الدالة بقراءة الملفات النصية، وتقطيعها،
    ثم حفظها كـ Vectors محلياً ومجانياً باستخدام HuggingFace.
    """
    if not os.path.exists(DATA_PATH) or not os.listdir(DATA_PATH):
        print(
            f"⚠️ Please add the knowledge base .txt files to the '{DATA_PATH}' folder."
        )
        return None

    # 1. تحميل الملفات النصية
    documents = []
    for file in os.listdir(DATA_PATH):
        if file.endswith(".txt") or file.endswith(".md"):
            file_path = os.path.join(DATA_PATH, file)
            # استخدام TextLoader لأن الملف المرفق نصي
            loader = TextLoader(file_path, encoding="utf-8")
            documents.extend(loader.load())
            print(f"📥 Loaded: {file}")

    if not documents:
        print("⚠️ No valid text files found.")
        return None

    # 2. التقطيع (Chunking) مع الحفاظ على السياق
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200, length_function=len
    )
    chunks = text_splitter.split_documents(documents)
    print(f"✂️ Text split into {len(chunks)} logical chunks.")

    # 3. استخدام نموذج مجاني ومحلي من HuggingFace للـ Embeddings
    print("🧠 Initializing Free HuggingFace Embeddings (all-MiniLM-L6-v2)...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # 4. بناء قاعدة البيانات
    print("🏗️ Building Chroma Database (this may take a minute on first run)...")
    db = Chroma.from_documents(chunks, embeddings, persist_directory=CHROMA_PATH)
    print(f"✅ Free Vector DB successfully built and saved in '{CHROMA_PATH}'!")
    return db


def get_retriever():
    """
    يستدعي هذه الدالة Agent 2 لاحقاً للبحث.
    """
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)
    return db.as_retriever(search_kwargs={"k": 4})


if __name__ == "__main__":
    build_vector_db()
