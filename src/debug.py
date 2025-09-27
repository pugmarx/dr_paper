from langchain_community.document_loaders import PyPDFLoader

loader = PyPDFLoader("paper1.pdf")
documents = loader.load()

print(f"Loaded {len(documents)} pages")
print(documents[0].page_content[:500]) 


from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=100,
    separators=["\n\n", "\n", ".", " "]
)
docs = splitter.split_documents(documents)

filtered_docs = [
    doc for doc in docs
    if len(doc.page_content.strip()) > 100 and "@" not in doc.page_content and not doc.page_content.lower().startswith("references")
]

print(f"Split into {len(docs)} chunks")
#print(docs[0].page_content[:300])
print(filtered_docs[0].page_content[:300])


from langchain_ollama import OllamaEmbeddings
#Afrom langchain.vectorstores import FAISS
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_ollama import ChatOllama

embeddings = OllamaEmbeddings(model="mistral")
#vectorstore = FAISS.from_documents(docs, embeddings)
vectorstore = FAISS.from_documents(filtered_docs, embeddings)

similar = vectorstore.similarity_search("Summarize the document", k=1)
print("--- Most relevant chunk ---")
print(similar[0].page_content[:500])

