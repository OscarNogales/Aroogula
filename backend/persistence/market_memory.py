from FlagEmbedding import BGEM3FlagModel
import chromadb
import numpy as np




class MarketMemory():
    def __init__(self, db_path: str):
        self.db_path: str = db_path
        self.collection = self.load()
        self.bge_model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=False, devices=['cpu'])

    def load(self):
        print("Connecting to Vector Universe...")
        client = chromadb.PersistentClient(path=self.db_path)
        

        collection = client.get_or_create_collection(
            name="market_memories",
            metadata={"hnsw:space": "cosine"}
        )
        print("Memory Vault Ready!")
        return collection

    def vectorize_string(self, texts: str | list[str]) -> np.ndarray:
        embedding = self.bge_model.encode(texts,
                                batch_size=64,
                                max_length=1024)['dense_vecs']
        
        return embedding
    
    def save_memory(self, ticker: str, database_id: str, text: str, vector_array: list, macro_state: dict, ai_decision: str) -> None:
        """Packages a single event and saves it to the vector database."""
        unique_id: str = f"{ticker}_{database_id}"
        
        full_metadata: dict = macro_state.copy()
        full_metadata["ticker"] = ticker
        full_metadata["ai_decision"] = ai_decision
        
        # Filtro estricto para ChromaDB: Solo acepta str, int, float o bool
        clean_metadata: dict = {}
        for key, value in full_metadata.items():
            if value is not None:
                if isinstance(value, (str, int, float, bool)):
                    clean_metadata[key] = value
                else:
                    clean_metadata[key] = str(value) # Convierte diccionarios/listas a texto

        # Convertimos el array de numpy a lista nativa si es necesario
        vector_list: list = vector_array.tolist() if hasattr(vector_array, 'tolist') else vector_array

        self.collection.upsert(
            ids=[unique_id],
            documents=[text],
            embeddings=[vector_list],
            metadatas=[clean_metadata]
        )

    def update_memory_sell(self, ticker: str, database_id: str, decision: str, macro_state: dict) -> None:
        """Updates the chromadb memory associated with the sell event."""
        unique_id: str = f"{ticker}_{database_id}"
        ai_sell_decision: str = decision if decision else "No sell decision associated..."
        
        try:
            results: dict = self.collection.get(ids=[unique_id])

            if not results or not results['ids']:
                print(f"⚠️ Could not find memory {unique_id} to update.")
                return

            current_metadata: dict = results['metadatas'][0]

            # Los guardamos como string para no romper las reglas de ChromaDB
            current_metadata['macro_state_sell'] = str(macro_state)
            current_metadata['sell_decision'] = ai_sell_decision

            self.collection.update(
                ids=[unique_id],
                metadatas=[current_metadata]
            )
            print(f"🧠 Memory {unique_id} successfully updated with sell data!")

        except Exception as e:
            print(f"⚠️ Update failed: {e}")
        
    def search_memory(self, ticker: str, current_vector: list, num_results: int = 3) -> dict | None:
        """Searches the vector database for the most similar past events for a specific ticker."""
        vector_list: list = current_vector.tolist() if hasattr(current_vector, 'tolist') else current_vector

        print(f"🔍 Searching past memories for {ticker}...", end="   ", flush=True)
        
        try:
            results: dict = self.collection.query(
                query_embeddings=[vector_list],
                n_results=num_results,
                where={"ticker": ticker} 
            )

            found_ids: list = results.get("ids", [[]])[0]
            print(f"🧠 Found {len(found_ids)} mathematically similar past events!")

            return results
            
        except Exception as e:
            print(f"⚠️ Memory search failed: {e}")
            return None

    def format_memory_for_prompt(self, chroma_results: dict, max_distance: float = 1.0) -> str:
        """
        Unpacks ChromaDB results, filters out bad matches, 
        and formats them into plain English for the LLM.
        """
        if not chroma_results or not chroma_results.get("ids") or len(chroma_results["ids"][0]) == 0:
            return "No relevant historical memories found for this ticker."

        memory_string: str = "--- RELEVANT PAST MEMORIES ---\n"
        found_valid_memory: bool = False

        distances: list = chroma_results.get("distances", [[]])[0] if chroma_results.get("distances") else []
        documents: list = chroma_results.get("documents", [[]])[0] if chroma_results.get("documents") else []
        metadatas: list = chroma_results.get("metadatas", [[]])[0] if chroma_results.get("metadatas") else []

        for i in range(len(distances)):
            dist: float = distances[i]
            
            if dist > max_distance:
                continue
                
            found_valid_memory = True
            text: str = documents[i]
            meta: dict = metadatas[i] if metadatas[i] is not None else {}
            
            memory_string += f"\n[Past Event {i+1} - Distance: {round(dist, 2)}]\n"
            memory_string += f"News Summary: {text}\n"
            memory_string += f"Macro State at the time: VIX={meta.get('vix_level', 'N/A')}, SPY Trend={meta.get('sp500_trend_pct', 'N/A')}%, Rates={meta.get('interest_rate', 'N/A')}%\n"
            memory_string += f"Your Past Decision: {meta.get('ai_decision', 'N/A')}\n"
            memory_string += "-" * 30 + "\n"

        if not found_valid_memory:
            return "Past events were found in the database, but none were mathematically similar enough to be relevant."

        return memory_string

