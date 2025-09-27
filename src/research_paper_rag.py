import os
import argparse
import warnings
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA

from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_ollama import ChatOllama

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore")


def load_or_create_index(pdf_path: str, model_name="mistral") -> FAISS:
    embeddings = OllamaEmbeddings(model=model_name)

    pdf_id = os.path.splitext(os.path.basename(pdf_path))[0]
    data_dir = ".data"
    index_dir = os.path.join(data_dir, f"faiss_index_{pdf_id}")
    
    # Create .data directory if it doesn't exist
    os.makedirs(data_dir, exist_ok=True)

    if os.path.exists(index_dir):
        print("Loading context...")
        return FAISS.load_local(index_dir, embeddings, allow_dangerous_deserialization=True)

    print("Parsing context...")
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        separators=["\n\n", "\n", ".", " "]
    )
    chunks = splitter.split_documents(documents)

    # Optional: simple filtering
    filtered_chunks = [
        doc for doc in chunks
        if len(doc.page_content.strip()) > 100 and "@" not in doc.page_content and not doc.page_content.lower().startswith("references")
    ]

    vectorstore = FAISS.from_documents(filtered_chunks, embeddings)
    vectorstore.save_local(index_dir)
    print("Context ready.")
    return vectorstore

def chat_with_paper(pdf_path: str, query: str, model_name="mistral"):
    vectorstore = load_or_create_index(pdf_path, model_name)
    llm = ChatOllama(model=model_name)

    print("Generating response...")
    
    # Setup retrieval
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    qa = RetrievalQA.from_chain_type(
        llm=llm, 
        retriever=retriever, 
        chain_type="stuff",
        return_source_documents=True
    )

    response = qa.invoke({"query": query})
    
    # Clean output - just show the result
    print("\n" + "="*60)
    print(response['result'])
    print("="*60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ask questions about a PDF using LLM + RAG")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("query", help="Question to ask")
    parser.add_argument("--model", default="mistral", help="Ollama model to use (default: mistral)")

    args = parser.parse_args()
    chat_with_paper(args.pdf_path, args.query, args.model)

