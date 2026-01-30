"""Q&A Page - Ask questions about the document using RAG."""

import streamlit as st
from pathlib import Path
import sys
import os

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

st.set_page_config(page_title="Q&A | Jaanch Lite", page_icon="💬", layout="wide")

st.markdown("## 💬 Document Q&A")
st.markdown("Ask questions about your document using semantic search and legal reranking.")

# Check if document is loaded
if not st.session_state.get("chunks"):
    st.warning("⚠️ No document loaded. Please upload a document first.")
    st.page_link("pages/1_Upload_Parse.py", label="Go to Upload & Parse", icon="📄")
    st.stop()

# Check API keys
has_voyage = bool(os.getenv("VOYAGE_API_KEY"))
has_gemini = bool(os.getenv("GOOGLE_API_KEY"))

if not has_voyage:
    st.error("⚠️ VOYAGE_API_KEY not set. Required for embeddings and reranking.")
    st.stop()

# Display current document
st.info(f"📄 Current document: **{st.session_state.get('current_doc', 'Unknown')}** ({len(st.session_state.chunks)} chunks)")

# Initialize document store if not exists
if "doc_store_initialized" not in st.session_state:
    st.session_state.doc_store_initialized = False
    st.session_state.doc_store = None

# Initialize document store button
if not st.session_state.doc_store_initialized:
    st.markdown("### 🔧 Setup Required")
    st.markdown("Index the document chunks for semantic search.")

    if st.button("📊 Index Document", type="primary", use_container_width=True):
        with st.spinner("Indexing document with Voyage AI embeddings..."):
            try:
                from src.search.rag import DocumentStore

                progress = st.progress(0, text="Initializing Voyage AI...")

                # Create document store
                doc_store = DocumentStore(
                    collection_name="streamlit_session",
                    db_path="./vectordb/streamlit"
                )

                progress.progress(30, text="Embedding chunks...")

                # Add chunks to store
                doc_store.add_chunks(st.session_state.chunks)

                progress.progress(100, text="Done!")

                st.session_state.doc_store = doc_store
                st.session_state.doc_store_initialized = True

                st.success(f"✅ Indexed {len(st.session_state.chunks)} chunks")
                st.rerun()

            except Exception as e:
                st.error(f"❌ Indexing failed: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
else:
    st.success("✅ Document indexed and ready for questions")

st.divider()

# Search settings
with st.expander("⚙️ Search Settings", expanded=False):
    col1, col2, col3 = st.columns(3)

    with col1:
        top_k = st.slider("Initial retrieval (top_k)", 5, 50, 20)

    with col2:
        rerank_k = st.slider("After reranking", 1, 10, 5)

    with col3:
        use_rerank = st.checkbox("Use Voyage Reranker", value=True)

# Chat interface
st.markdown("### 💬 Ask a Question")

# Display chat history
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        # Show sources for assistant messages
        if message["role"] == "assistant" and message.get("sources"):
            with st.expander("📚 Sources", expanded=False):
                for i, source in enumerate(message["sources"]):
                    st.markdown(f"**[{i+1}]** Page {source.get('page', '?')} | {source.get('type', 'text')}")
                    st.text(source.get("text", "")[:300] + "..." if len(source.get("text", "")) > 300 else source.get("text", ""))
                    st.divider()

# Chat input
if prompt := st.chat_input("Ask a question about the document...", disabled=not st.session_state.doc_store_initialized):
    # Add user message
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Searching..."):
            try:
                doc_store = st.session_state.doc_store

                # Search
                if use_rerank:
                    from src.search.rag import RAGSearch

                    rag = RAGSearch(doc_store)
                    response = rag.search(
                        query=prompt,
                        top_k=rerank_k,
                        rerank=True,
                        rerank_instruction="Find passages that directly answer this legal question with specific details."
                    )
                    # Extract results from SearchResponse
                    search_results = response.results
                else:
                    # Direct vector search returns list of dicts
                    search_results = doc_store.search(prompt, top_k=rerank_k)

                # Format response
                if search_results:
                    # Build context
                    context_parts = []
                    sources = []

                    for i, result in enumerate(search_results):
                        # Handle both SearchResult objects and dicts
                        if hasattr(result, 'chunk'):
                            # SearchResult object from RAG
                            chunk = result.chunk
                            score = result.score
                        else:
                            # Dict from direct search
                            chunk = type('Chunk', (), {
                                'text': result['text'],
                                'page': result['page'],
                                'chunk_type': result['chunk_type']
                            })()
                            score = result.get("similarity", 0)

                        context_parts.append(f"[{i+1}] {chunk.text}")
                        sources.append({
                            "page": chunk.page,
                            "type": chunk.chunk_type.value if hasattr(chunk.chunk_type, 'value') else str(chunk.chunk_type),
                            "text": chunk.text,
                            "score": score,
                        })

                    # Generate answer with Gemini if available
                    if has_gemini:
                        try:
                            from google import genai

                            client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

                            context = "\n\n".join(context_parts)
                            gen_prompt = f"""Based on the following document excerpts, answer the question.

Question: {prompt}

Document excerpts:
{context}

Provide a clear, concise answer based only on the information in the excerpts. Cite the source numbers [1], [2], etc. where relevant."""

                            response = client.models.generate_content(
                                model="gemini-2.0-flash",
                                contents=gen_prompt
                            )
                            answer = response.text

                        except Exception as e:
                            error_str = str(e)
                            if "429" in error_str or "quota" in error_str.lower():
                                st.warning("Gemini quota exceeded. Showing search results only.")
                            else:
                                st.warning(f"Gemini error: {error_str[:150]}")
                            # Fallback to showing excerpts
                            answer = f"**Relevant passages found:**\n\n"
                            for i, source in enumerate(sources[:3]):
                                answer += f"**[{i+1}]** (Page {source['page']}, {source['score']:.2f})\n{source['text'][:500]}...\n\n"
                    else:
                        # No Gemini - show excerpts
                        answer = f"**Found {len(search_results)} relevant passages:**\n\n"
                        for i, source in enumerate(sources[:3]):
                            answer += f"**[{i+1}]** (Page {source['page']})\n{source['text'][:500]}...\n\n"

                    st.markdown(answer)

                    # Show sources
                    with st.expander("📚 Sources", expanded=False):
                        for i, source in enumerate(sources):
                            st.markdown(f"**[{i+1}]** Page {source['page']} | {source['type']} | Score: {source['score']:.3f}")
                            st.text(source["text"][:300] + "..." if len(source["text"]) > 300 else source["text"])
                            st.divider()

                    # Save to history
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": answer,
                        "sources": sources
                    })

                else:
                    no_results = "No relevant passages found for your question. Try rephrasing or asking something else."
                    st.markdown(no_results)
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": no_results,
                        "sources": []
                    })

            except Exception as e:
                error_msg = f"❌ Search failed: {str(e)}"
                st.error(error_msg)
                import traceback
                st.code(traceback.format_exc())

# Sidebar
with st.sidebar:
    st.markdown("### 💬 Chat History")

    if st.session_state.chat_history:
        st.metric("Messages", len(st.session_state.chat_history))

        if st.button("🗑️ Clear History"):
            st.session_state.chat_history = []
            st.rerun()
    else:
        st.info("No messages yet")

    st.divider()

    st.markdown("### 🔍 Search Info")
    st.markdown(f"""
    - **Embeddings:** Voyage voyage-law-2
    - **Reranker:** Voyage rerank-2.5
    - **Vector DB:** ChromaDB
    - **LLM:** Gemini 2.5 Flash
    """)

    st.divider()

    st.markdown("### 💡 Example Questions")
    st.markdown("""
    - What are the main provisions?
    - Who are the parties involved?
    - What penalties are mentioned?
    - Summarize section 3
    """)
